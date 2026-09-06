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
      # Validate path is within allowed roots and return it as an absolute path.
      # Relative paths are resolved against the workspace (the client's project
      # directory), not against the SketchUp process working directory.
      # @param path [String, nil] path to validate
      # @param operation [String] operation name for error messages
      # @param workspace [String, nil] optional workspace to include in allowed roots
      # @return [String, nil] absolute path, or nil when path is nil
      # @raise [PathAccessDenied] if path is not allowed
      def validate!(path, operation: 'access', workspace: nil)
        return unless path

        absolute = absolute_path(path, workspace: workspace)
        return absolute if allow_all?

        resolved = resolve_path(absolute)
        return absolute if allowed?(resolved, workspace: workspace)

        raise PathAccessDenied, "Path access denied for #{operation}: #{path}"
      end

      # Expand path to an absolute path, resolving relative paths against the workspace
      # @param path [String] path to expand
      # @param workspace [String, nil] base directory for relative paths
      # @return [String] absolute path
      def absolute_path(path, workspace: nil)
        base = workspace && !workspace.empty? ? File.expand_path(workspace) : nil
        File.expand_path(path, base)
      end

      # Check if path is within allowed roots
      # @param resolved_path [String] resolved path
      # @param workspace [String, nil] optional workspace to include
      # @return [Boolean]
      def allowed?(resolved_path, workspace: nil)
        roots = allowed_roots(workspace: workspace)
        roots.any? { |root| path_within?(resolved_path, root) }
      end

      # Get list of allowed roots (canonicalized to match resolve_path output)
      # @param workspace [String, nil] optional workspace to include
      # @return [Array<String>]
      def allowed_roots(workspace: nil)
        roots = ALLOWED_ROOTS.dup
        roots << workspace if workspace && !workspace.empty?
        roots.map { |r| resolve_path(r) }.uniq
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
        return File.realpath(expanded) if File.exist?(expanded)

        # For non-existing files (write targets): resolve symlinks in the
        # nearest existing ancestor to prevent symlinked parent escape.
        canonical_parent = resolve_nearest_ancestor(expanded)
        remaining = expanded.sub(/^#{Regexp.escape(find_nearest_ancestor(expanded))}/, '')
        File.join(canonical_parent, remaining)
      end

      # Walk up from path until we find an existing ancestor directory.
      # Returns the expanded (non-canonical) path of that ancestor.
      # @raise [PathAccessDenied] if no ancestor exists (e.g. broken root)
      def find_nearest_ancestor(path)
        current = File.dirname(path)
        while current != '/'
          return current if File.exist?(current)

          current = File.dirname(current)
        end
        '/' # root always exists
      end

      # Canonicalize the nearest existing ancestor of a path.
      # @raise [PathAccessDenied] if ancestor is a broken symlink
      def resolve_nearest_ancestor(path)
        ancestor = find_nearest_ancestor(path)
        File.realpath(ancestor)
      rescue Errno::ENOENT
        raise PathAccessDenied, "Path denied: broken symlink in parent of #{path}"
      end

      def path_within?(path, root)
        path.start_with?(root + File::SEPARATOR) || path == root
      end
    end
  end
end
