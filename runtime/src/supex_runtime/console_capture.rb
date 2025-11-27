# frozen_string_literal: true

module SupexRuntime
  # Console output capture for debugging and feedback
  class ConsoleCapture
    attr_reader :log_file_path, :original_stdout, :original_stderr

    def initialize(log_file_path)
      @log_file_path = log_file_path
      @original_stdout = $stdout
      @original_stderr = $stderr
      @log_file = nil
      @capture_enabled = false

      ensure_log_directory
      initialize_log_file
    end

    # Start capturing console output
    def start_capture
      return if @capture_enabled

      begin
        @log_file = File.open(@log_file_path, 'a')
        @log_file.sync = true

        # Add session marker
        session_marker = "\n#{'=' * 50}\n"
        session_marker += "SketchUp Console Session Started: #{Time.now}\n"
        session_marker += "Supex Extension Version: #{VERSION}\n"
        session_marker += "#{'=' * 50}\n"
        @log_file.write(session_marker)

        # Replace stdout and stderr with capture instances
        $stdout = OutputCapture.new(@original_stdout, @log_file, 'STDOUT')
        $stderr = OutputCapture.new(@original_stderr, @log_file, 'STDERR')

        @capture_enabled = true
        puts "Supex: Console capture started - output will be logged to: #{@log_file_path}"
      rescue StandardError => e
        # Fallback gracefully if capture fails
        puts "Supex: Warning: Could not start console capture: #{e.message}"
        @capture_enabled = false
      end
    end

    # Stop capturing console output
    def stop_capture
      return unless @capture_enabled

      begin
        # Add session end marker
        if @log_file && !@log_file.closed?
          session_end = "\nConsole Session Ended: #{Time.now}\n"
          session_end += "#{'-' * 50}\n"
          @log_file.write(session_end)
        end

        # Restore original streams
        $stdout = @original_stdout
        $stderr = @original_stderr

        # Close log file
        @log_file&.close
        @log_file = nil
        @capture_enabled = false

        puts 'Supex: Console capture stopped'
      rescue StandardError => e
        puts "Supex: Warning: Error stopping console capture: #{e.message}"
      end
    end

    # Check if capture is currently active
    def capturing?
      @capture_enabled
    end

    # Add a custom marker to the log
    def add_marker(message)
      return unless @capture_enabled && @log_file && !@log_file.closed?

      begin
        marker = "\n--- #{message} [#{Time.now.strftime('%H:%M:%S')}] ---\n"
        @log_file.write(marker)
        @log_file.flush
      rescue StandardError => e
        puts "Supex: Warning: Could not write marker to log: #{e.message}"
      end
    end

    private

    # Ensure the log directory exists
    def ensure_log_directory
      log_dir = File.dirname(@log_file_path)
      FileUtils.mkdir_p(log_dir)
    rescue StandardError => e
      puts "Supex: Warning: Could not create log directory: #{e.message}"
    end

    # Initialize log file with header
    def initialize_log_file
      return unless File.exist?(File.dirname(@log_file_path))

      begin
        # Check file size and rotate if necessary (limit to 5MB)
        if File.exist?(@log_file_path) && File.size(@log_file_path) > 5_242_880
          backup_path = "#{@log_file_path}.old"
          File.rename(@log_file_path, backup_path) if File.exist?(@log_file_path)
        end
      rescue StandardError => e
        puts "Supex: Warning: Could not rotate log file: #{e.message}"
      end
    end

    # Output capture wrapper class
    class OutputCapture
      def initialize(original_stream, log_file, stream_name)
        @original_stream = original_stream
        @log_file = log_file
        @stream_name = stream_name
      end

      def write(text)
        # Write to original stream (preserves console output)
        @original_stream.write(text)

        # Write to log file with timestamp and stream identifier
        begin
          if @log_file && !@log_file.closed?
            timestamp = Time.now.strftime('[%H:%M:%S]')
            log_text = text.each_line.map do |line|
              if line.strip.empty?
                line
              else
                "#{timestamp} #{@stream_name}: #{line}"
              end
            end.join

            @log_file.write(log_text)
            @log_file.flush
          end
        rescue StandardError => e
          # Don't break if logging fails - just continue with console output
          @original_stream.write("[Logging Error: #{e.message}]\n")
        end
      end

      def flush
        @original_stream.flush
        @log_file&.flush if @log_file && !@log_file.closed?
      end

      def puts(*args)
        if args.empty?
          write("\n")
        else
          args.each { |arg| write("#{arg}\n") }
        end
      end

      def print(*args)
        args.each { |arg| write(arg.to_s) }
      end

      def printf(format, *args)
        write(format % args)
      end

      # Delegate other methods to original stream
      def method_missing(method_name, *, &)
        @original_stream.send(method_name, *, &)
      end

      def respond_to_missing?(method_name, include_private = false)
        @original_stream.respond_to?(method_name, include_private)
      end
    end
  end
end
