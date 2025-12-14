# frozen_string_literal: true

module SupexRuntime
  # Path validation policy for file operations
  # This is a guardrail to prevent accidental writes to wrong directories,
  # NOT a security boundary (arbitrary Ruby execution bypasses it).
  module PathPolicy
    # Environment configuration for additional allowed paths
    ALLOWED_ROOTS = (ENV['SUPEX_ALLOWED_ROOTS'] || '').split(':').reject(&:empty?)

    # Exception raised when path access is denied
    class PathAccessDenied < StandardError; end

    class << self
      # Validate path is within allowed roots
      # @param path [String] path to validate
      # @param operation [String] operation name for error messages
      # @param workspace [String, nil] optional workspace to include in allowed roots
      # @raise [PathAccessDenied] if path is not allowed
      def validate!(path, operation: 'access', workspace: nil)
        return if allow_all?
        return unless path

        resolved = resolve_path(path)
        return if allowed?(resolved, workspace: workspace)

        raise PathAccessDenied, "Path access denied for #{operation}: #{path}"
      end

      # Check if path is within allowed roots
      # @param resolved_path [String] resolved path
      # @param workspace [String, nil] optional workspace to include
      # @return [Boolean]
      def allowed?(resolved_path, workspace: nil)
        roots = allowed_roots(workspace: workspace)
        roots.any? { |root| path_within?(resolved_path, root) }
      end

      # Get list of allowed roots
      # @param workspace [String, nil] optional workspace to include
      # @return [Array<String>]
      def allowed_roots(workspace: nil)
        roots = ALLOWED_ROOTS.dup
        roots << workspace if workspace && !workspace.empty?
        roots.map { |r| File.expand_path(r) }.uniq
      end

      # Get default .tmp directory for a workspace
      # @param workspace [String] workspace path
      # @return [String] path to .tmp directory
      # @raise [PathAccessDenied] if workspace is not set
      def default_tmp_dir(workspace)
        raise PathAccessDenied, 'workspace is required for default paths' unless workspace && !workspace.empty?

        File.join(File.expand_path(workspace), '.tmp')
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
