# frozen_string_literal: true

module SupexRuntime
  # Observer queue for tracking SketchUp model entity changes.
  # The driver polls this queue via vcad.observer_poll to detect
  # which entities were modified and trigger DAG cascade re-evaluation.
  class VcadObserverQueue
    DEFAULT_MAX_QUEUE = 2048

    def initialize(max_queue: nil)
      @max_queue = max_queue || ENV.fetch('VCAD_OBSERVER_MAX_QUEUE', DEFAULT_MAX_QUEUE.to_s).to_i
      @changed_ids = []
      @dropped = 0
      @mutex = Mutex.new
    end

    # Add entity IDs to the change queue (deduplicating).
    # @param entity_ids [Array<Integer>] entity IDs that changed
    def push(entity_ids)
      @mutex.synchronize do
        entity_ids.each do |eid|
          next if @changed_ids.include?(eid)

          if @changed_ids.length >= @max_queue
            @dropped += 1
          else
            @changed_ids << eid
          end
        end
      end
    end

    # Drain the queue and return all accumulated changes.
    # @return [Hash] changed_entity_ids, dropped count, queue_size
    def drain
      @mutex.synchronize do
        ids = @changed_ids.dup
        dropped = @dropped
        @changed_ids.clear
        @dropped = 0
        {
          changed_entity_ids: ids,
          dropped: dropped,
          queue_size: ids.length
        }
      end
    end

    # Clear the queue without returning contents.
    def clear
      @mutex.synchronize do
        @changed_ids.clear
        @dropped = 0
      end
    end

    # Current number of queued IDs.
    # @return [Integer]
    def size
      @mutex.synchronize { @changed_ids.length }
    end
  end

  # SketchUp ModelObserver that detects entity modifications and
  # enqueues changed entity IDs for the driver to poll.
  class VcadModelObserver < Sketchup::ModelObserver
    attr_reader :queue

    def initialize(queue)
      super()
      @queue = queue
    end

    # Called after a transaction (undo group) is committed.
    # Scan for changed entities and enqueue their IDs.
    def onTransactionCommit(model)
      changed_ids = collect_vcad_entity_ids(model)
      @queue.push(changed_ids) unless changed_ids.empty?
    end

    # Called after undo — treat the same as commit for change detection.
    def onTransactionUndo(model)
      changed_ids = collect_vcad_entity_ids(model)
      @queue.push(changed_ids) unless changed_ids.empty?
    end

    # Called after redo.
    def onTransactionRedo(model)
      changed_ids = collect_vcad_entity_ids(model)
      @queue.push(changed_ids) unless changed_ids.empty?
    end

    private

    # Collect entity IDs of all component instances in the model
    # that could affect vcad nodes (any instance or group at top level).
    # The driver's DAG determines whether these actually matter.
    def collect_vcad_entity_ids(model)
      ids = []
      model.active_entities.each do |entity|
        next unless entity.respond_to?(:entityID)
        next unless entity.is_a?(Sketchup::ComponentInstance) || entity.is_a?(Sketchup::Group)

        ids << entity.entityID
      end
      ids
    end
  end

  # Manages observer attachment/detachment lifecycle.
  module VcadObserverManager
    extend self

    @observer = nil
    @queue = nil

    # Start observing model changes.
    # @return [Hash] status information
    def start
      model = Sketchup.active_model
      raise 'No active model' unless model

      if @observer
        return { success: true, status: 'already_running', message: 'Observer already attached' }
      end

      @queue = VcadObserverQueue.new
      @observer = VcadModelObserver.new(@queue)
      model.add_observer(@observer)

      { success: true, status: 'started', message: 'Observer attached to model' }
    end

    # Stop observing model changes.
    # @return [Hash] status information
    def stop
      model = Sketchup.active_model

      unless @observer
        return { success: true, status: 'not_running', message: 'Observer was not attached' }
      end

      model&.remove_observer(@observer)
      @queue&.clear
      @observer = nil
      @queue = nil

      { success: true, status: 'stopped', message: 'Observer detached from model' }
    end

    # Poll for changes since last poll.
    # @return [Hash] changed_entity_ids, dropped, queue_size
    def poll
      unless @queue
        return { changed_entity_ids: [], dropped: 0, queue_size: 0 }
      end

      @queue.drain
    end

    # Whether the observer is currently attached.
    # @return [Boolean]
    def running?
      !@observer.nil?
    end
  end
end
