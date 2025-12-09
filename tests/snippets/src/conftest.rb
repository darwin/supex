# frozen_string_literal: true

# Ruby snippets for conftest.py fixtures
# All functions wrapped in SupexTestSnippets module to prevent naming conflicts

module SupexTestSnippets
  def self.fixture_clear_all
    model = Sketchup.active_model
    model.start_operation('Clear All', true)
    # Remove all entities
    model.entities.clear!
    # Remove all materials except defaults
    model.materials.to_a.each do |m|
      model.materials.remove(m)
    rescue
      nil
    end
    # Remove all layers except Layer0
    model.layers.to_a.each do |l|
      model.layers.remove(l) if l.name != 'Layer0'
    rescue
      nil
    end
    # Remove all component definitions except built-ins
    model.definitions.to_a.each do |d|
      model.definitions.remove(d) if !d.image? && !d.group?
    rescue
      nil
    end
    model.commit_operation
    true
  end
end
