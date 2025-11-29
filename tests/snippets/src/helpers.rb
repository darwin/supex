# Ruby snippets for helper functions
# All functions wrapped in SupexTestSnippets module to prevent naming conflicts

module SupexTestSnippets
  def self.fixture_clear_entities
    model = Sketchup.active_model
    model.start_operation('Clear Model', true)
    model.entities.clear!
    model.commit_operation
    model.entities.length
  end
end
