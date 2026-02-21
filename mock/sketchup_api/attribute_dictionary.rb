# frozen_string_literal: true

# Attribute dictionary mixin for all SketchUp entities.
# Provides set_attribute/get_attribute matching SketchUp API semantics.
module SketchupMock
  module AttributeDictionary
    def set_attribute(dict, key, value)
      @attribute_dictionaries ||= {}
      @attribute_dictionaries[dict] ||= {}
      @attribute_dictionaries[dict][key] = value
    end

    def get_attribute(dict, key, default = nil)
      @attribute_dictionaries ||= {}
      val = @attribute_dictionaries.dig(dict, key)
      val.nil? ? default : val
    end

    def attribute_dictionaries
      @attribute_dictionaries ||= {}
    end
  end
end
