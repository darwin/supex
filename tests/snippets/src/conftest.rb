# Ruby snippets for conftest.py fixtures
# All functions wrapped in SupexTestSnippets module to prevent naming conflicts

module SupexTestSnippets
  def self.fixture_clear_all
    model = Sketchup.active_model
    model.start_operation('Clear All', true)
    # Remove all entities
    model.entities.clear!
    # Remove all materials except defaults
    model.materials.to_a.each { |m| model.materials.remove(m) rescue nil }
    # Remove all layers except Layer0
    model.layers.to_a.each { |l| model.layers.remove(l) if l.name != 'Layer0' rescue nil }
    # Remove all component definitions except built-ins
    model.definitions.to_a.each { |d| model.definitions.remove(d) if !d.image? && !d.group? rescue nil }
    model.commit_operation
    true
  end
end
