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

        # Add session marker in pipe-separated format for Ideolog
        @log_file.write("\n")
        @log_file.write(idea_log_line('I', '=' * 50))
        @log_file.write(idea_log_line('I', 'Session Started'))
        @log_file.write(idea_log_line('I', '=' * 50))

        # Replace stdout and stderr with capture instances
        $stdout = OutputCapture.new(@original_stdout, @log_file, 'STDOUT', 'I')
        $stderr = OutputCapture.new(@original_stderr, @log_file, 'STDERR', 'E')

        @capture_enabled = true
        log_status "Console capture started - output will be logged to: #{@log_file_path}"
      rescue StandardError => e
        # Fallback gracefully if capture fails
        log_status "Warning: Could not start console capture: #{e.message}"
        @capture_enabled = false
      end
    end

    # Stop capturing console output
    def stop_capture
      return unless @capture_enabled

      begin
        # Add session end marker in pipe-separated format
        if @log_file && !@log_file.closed?
          @log_file.write(idea_log_line('I', '=' * 50))
          @log_file.write(idea_log_line('I', 'Session Ended'))
          @log_file.write(idea_log_line('I', '=' * 50))
        end

        # Restore original streams
        $stdout = @original_stdout
        $stderr = @original_stderr

        # Close log file
        @log_file&.close
        @log_file = nil
        @capture_enabled = false

        log_status 'Console capture stopped'
      rescue StandardError => e
        log_status "Warning: Error stopping console capture: #{e.message}"
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
        @log_file.write(idea_log_line('D', "Supex: --- #{message} ---"))
        @log_file.flush
      rescue StandardError => e
        puts "Supex: Warning: Could not write marker to log: #{e.message}"
      end
    end

    private

    # Log status message (silent in test mode)
    def log_status(message)
      return if ENV['SUPEX_SILENT'] == '1'

      puts "Supex: #{message}"
    end

    # Format a log line in pipe-separated format for Ideolog
    def idea_log_line(severity, message)
      timestamp = Time.now.strftime('%H:%M:%S.%L')
      "#{timestamp}|#{severity}|SketchUp|#{message}\n"
    end

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
      def initialize(original_stream, log_file, stream_name, severity)
        @original_stream = original_stream
        @log_file = log_file
        @stream_name = stream_name
        @severity = severity
      end

      def write(text)
        # Write to original stream (preserves console output)
        @original_stream.write(text)

        # Write to log file in pipe-separated format for Ideolog
        begin
          if @log_file && !@log_file.closed?
            log_text = text.each_line.map do |line|
              if line.strip.empty?
                line
              else
                "#{idea_format(@severity, line.chomp)}\n"
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

      private

      def idea_format(severity, message)
        timestamp = Time.now.strftime('%H:%M:%S.%L')
        "#{timestamp}|#{severity}|SketchUp|#{message}"
      end
    end
  end
end
