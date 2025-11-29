#!/usr/bin/env python3
"""
Ruby-based 3D modeling example for Supex

This example demonstrates creating 3D models using SketchUp's Ruby API
via the eval_ruby tool - the primary interface for all modeling operations.
"""

import json
from supex_driver.adapter.connection import get_sketchup_connection

def main():
    """Create 3D models using SketchUp Ruby API"""
    print("Supex Ruby Modeling Example")
    print("=" * 40)
    
    try:
        # Get connection to SketchUp
        print("Connecting to SketchUp...")
        sketchup = get_sketchup_connection()
        print("✓ Connected to SketchUp")
        
        # Clear the scene first
        print("\nClearing scene...")
        clear_code = """
        model = Sketchup.active_model
        entities = model.active_entities
        entities.clear!
        puts "Scene cleared"
        """
        sketchup.send_command("eval_ruby", {"code": clear_code})
        
        # Create a table using Ruby
        print("\nCreating table with Ruby API...")
        table_code = """
        model = Sketchup.active_model
        entities = model.active_entities
        
        # Create table top
        table_top = entities.add_group
        table_top.name = "Table Top"
        top_face = table_top.entities.add_face(
          [0, 0, 2.feet], [4.feet, 0, 2.feet],
          [4.feet, 6.feet, 2.feet], [0, 6.feet, 2.feet]
        )
        top_face.pushpull(2.inches)
        
        # Apply wood material to table top
        wood_material = model.materials.add("Wood")
        wood_material.color = [139, 69, 19]  # Saddle brown
        table_top.material = wood_material
        
        # Create table legs
        leg_positions = [
          [0.5.feet, 0.5.feet, 0],
          [3.5.feet, 0.5.feet, 0], 
          [0.5.feet, 5.5.feet, 0],
          [3.5.feet, 5.5.feet, 0]
        ]
        
        leg_positions.each_with_index do |pos, i|
          leg = entities.add_group
          leg.name = "Table Leg #{i + 1}"
          
          # Create circular leg base
          center = [pos[0], pos[1], pos[2]]
          circle = leg.entities.add_circle(center, [0, 0, 1], 2.inches)
          leg_face = leg.entities.add_face(circle)
          leg_face.pushpull(2.feet)
          
          leg.material = wood_material
        end
        
        puts "Table created with 4 legs"
        """
        
        result = sketchup.send_command("eval_ruby", {"code": table_code})
        print("✓ Table created successfully")
        
        # Create decorative objects
        print("\nAdding decorative objects...")
        decoration_code = """
        # Create a vase using Ruby
        vase = entities.add_group
        vase.name = "Decorative Vase"
        
        # Create vase base circle
        vase_center = [2.feet, 3.feet, 2.feet + 2.inches]
        vase_circle = vase.entities.add_circle(vase_center, [0, 0, 1], 4.inches)
        vase_base = vase.entities.add_face(vase_circle)
        vase_base.pushpull(8.inches)
        
        # Apply blue material
        blue_material = model.materials.add("Blue Ceramic")
        blue_material.color = [65, 105, 225]  # Royal blue
        vase.material = blue_material
        
        # Create a lamp with sphere shade
        lamp_base = entities.add_group
        lamp_base.name = "Lamp Base"
        
        # Cylindrical base
        base_center = [3.feet, 1.feet, 2.feet + 2.inches]
        base_circle = lamp_base.entities.add_circle(base_center, [0, 0, 1], 3.inches)
        base_face = lamp_base.entities.add_face(base_circle)
        base_face.pushpull(12.inches)
        
        # Dark material for base
        dark_material = model.materials.add("Dark Metal")
        dark_material.color = [47, 79, 79]  # Dark slate gray
        lamp_base.material = dark_material
        
        # Spherical lamp shade
        lamp_shade = entities.add_group
        lamp_shade.name = "Lamp Shade"
        
        # Create sphere using latitude/longitude method
        shade_center = [3.feet, 1.feet, 2.feet + 14.inches]
        sphere_radius = 6.inches
        
        # Create sphere geometry
        16.times do |lat|
          latitude = -90 + (lat * 180.0 / 15)
          lat_rad = latitude * Math::PI / 180
          
          circle_radius = sphere_radius * Math.cos(lat_rad)
          circle_center = [
            shade_center[0],
            shade_center[1], 
            shade_center[2] + sphere_radius * Math.sin(lat_rad)
          ]
          
          if circle_radius > 0.1.inches
            circle = lamp_shade.entities.add_circle(circle_center, [0, 0, 1], circle_radius, 12)
          end
        end
        
        # Light material for shade
        light_material = model.materials.add("Light Shade")
        light_material.color = [255, 248, 220]  # Cornsilk
        lamp_shade.material = light_material
        
        puts "Decorative objects added"
        """
        
        sketchup.send_command("eval_ruby", {"code": decoration_code})
        print("✓ Decorative objects added")
        
        # Create room elements
        print("\nAdding room elements...")
        room_code = """
        # Create floor
        floor = entities.add_group
        floor.name = "Floor"
        floor_face = floor.entities.add_face(
          [-2.feet, -2.feet, 0], [8.feet, -2.feet, 0],
          [8.feet, 10.feet, 0], [-2.feet, 10.feet, 0]
        )
        
        # Floor material
        floor_material = model.materials.add("Hardwood Floor")
        floor_material.color = [222, 184, 135]  # Burlywood
        floor.material = floor_material
        
        # Create wall
        wall = entities.add_group
        wall.name = "Back Wall"
        wall_face = wall.entities.add_face(
          [-2.feet, -2.feet, 0], [-2.feet, -2.feet, 8.feet],
          [-2.feet, 10.feet, 8.feet], [-2.feet, 10.feet, 0]
        )
        
        # Wall material
        wall_material = model.materials.add("Wall Paint")
        wall_material.color = [245, 245, 220]  # Beige
        wall.material = wall_material
        
        puts "Room elements completed"
        """
        
        sketchup.send_command("eval_ruby", {"code": room_code})
        print("✓ Room elements added")
        
        # Summary
        print("\n" + "=" * 40)
        print("✓ Ruby modeling example completed successfully!")
        print("Created using SketchUp Ruby API:")
        print("  • Table with named components (top + 4 legs)")
        print("  • Decorative vase with ceramic material")
        print("  • Table lamp with base and spherical shade")
        print("  • Room elements (floor and wall)")
        print("  • Multiple materials and proper organization")
        print("\nAll geometry created via eval_ruby tool using native SketchUp API!")
        
        # Optionally export the scene
        export_choice = input("\nWould you like to export the scene? (y/N): ")
        if export_choice.lower() == 'y':
            print("Exporting scene as OBJ file...")
            export_result = sketchup.send_command(
                "export_scene",
                {"format": "obj"}
            )
            print(f"✓ Scene exported to: {export_result['path']}")
        
    except Exception as e:
        print(f"✗ Error: {e}")
        print("Make sure SketchUp is running and the SUP-MCP extension is started.")

if __name__ == "__main__":
    main()