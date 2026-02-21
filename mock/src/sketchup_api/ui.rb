# frozen_string_literal: true

# Mock UI module with blocking loop mode for headless operation.
# In real SketchUp, UI.start_timer runs callbacks on the UI thread.
# In su-mock, enable_blocking_mode! switches to a direct blocking loop.

# Mock menu
class MockMenu
  attr_reader :name, :items, :submenus

  def initialize(name)
    @name = name
    @items = []
    @submenus = {}
  end

  def add_item(label, &block)
    @items << { label: label, block: block }
    @items.length - 1
  end

  def add_separator
    @items << { separator: true }
  end

  def add_submenu(name)
    @submenus[name] ||= MockMenu.new(name)
  end
end

# Messagebox constants
MB_OK = 0
MB_OKCANCEL = 1
MB_YESNO = 4
MB_YESNOCANCEL = 3

module UI
  @timers = {}
  @timer_id = 0
  @messageboxes = []
  @menus = {}
  @blocking_mode = false
  @blocking_timer = nil
  @running = false

  class << self
    attr_accessor :messageboxes, :menus
    attr_reader :timers

    def start_timer(interval, repeat = false, &block)
      @timer_id += 1
      timer = { interval: interval, repeat: repeat, block: block }
      @timers[@timer_id] = timer

      # In blocking mode, capture the repeating timer for the blocking loop
      @blocking_timer = timer if @blocking_mode && repeat

      @timer_id
    end

    def stop_timer(id)
      timer = @timers.delete(id)
      @blocking_timer = nil if timer && @blocking_timer == timer
    end

    def clear_timers
      @timers.clear
      @timer_id = 0
      @blocking_timer = nil
    end

    def messagebox(message, type = MB_OK)
      @messageboxes ||= []
      @messageboxes << { message: message, type: type }
      1 # Return OK
    end

    def menu(name)
      @menus ||= {}
      @menus[name] ||= MockMenu.new(name)
    end

    # Switch to blocking mode (for headless operation without SketchUp UI thread)
    def enable_blocking_mode!
      @blocking_mode = true
    end

    def blocking_mode?
      @blocking_mode
    end

    # Run the blocking loop — calls the captured timer block in a loop.
    # This replaces SketchUp's UI thread event loop.
    def run_blocking_loop!
      raise 'No timer registered — call server.start before run_blocking_loop!' unless @blocking_timer

      @running = true
      interval = @blocking_timer[:interval]
      block = @blocking_timer[:block]

      while @running
        begin
          block.call
        rescue StandardError => e
          warn "Timer handler error: #{e.message}"
          warn e.backtrace.join("\n")
        end
        sleep(interval)
      end
    end

    # Stop the blocking loop (called from signal handler or test control)
    def stop_blocking_loop!
      @running = false
    end

    def reset_ui_mocks
      @messageboxes = []
      @menus = {}
      @blocking_mode = false
      @blocking_timer = nil
      @running = false
      clear_timers
    end
  end
end
