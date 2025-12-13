# frozen_string_literal: true

module SupexRuntime
  # Path validation policy for file operations
  # Restricts file access to configured roots to prevent traversal attacks
  module PathPolicy
    # Environment configuration
    ALLOWED_ROOTS = (ENV['SUPEX_ALLOWED_ROOTS'] || '').split(':').reject(&:empty?)
    PROJECT_ROOT = ENV['SUPEX_PROJECT_ROOT']

    # Default allowed: .tmp directory relative to runtime
    DEFAULT_TMP = File.expand_path('../../../.tmp', __dir__)

    # Exception raised when path access is denied
    class PathAccessDenied < StandardError; end

    class << self
      # Validate path is within allowed roots
      # @param path [String] path to validate
      # @param operation [String] operation name for error messages
      # @raise [PathAccessDenied] if path is not allowed
      def validate!(path, operation: 'access')
        return if allow_all?
        return unless path

        resolved = resolve_path(path)
        return if allowed?(resolved)

        raise PathAccessDenied, "Path access denied for #{operation}: #{path}"
      end

      # Check if path is within allowed roots
      # @param resolved_path [String] resolved path
      # @return [Boolean]
      def allowed?(resolved_path)
        allowed_roots.any? { |root| path_within?(resolved_path, root) }
      end

      # Get list of allowed roots for debugging
      # @return [Array<String>]
      def allowed_roots
        roots = ALLOWED_ROOTS.dup
        roots << PROJECT_ROOT if PROJECT_ROOT && !PROJECT_ROOT.empty?
        roots << DEFAULT_TMP
        roots.map { |r| File.expand_path(r) }.uniq
      end

      private

      def allow_all?
        ALLOWED_ROOTS.include?('*')
      end

      def resolve_path(path)
        expanded = File.expand_path(path)
        # Use realpath if file exists (resolves symlinks)
        File.exist?(expanded) ? File.realpath(expanded) : expanded
      end

      def path_within?(path, root)
        path.start_with?(root + File::SEPARATOR) || path == root
      end
    end
  end
end
