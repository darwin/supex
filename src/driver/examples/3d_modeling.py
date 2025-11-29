#!/usr/bin/env python3
"""
Ruby-based 3D Modeling example for Supex

This example demonstrates creating complex 3D models using SketchUp's Ruby API
via the eval_ruby tool. Shows advanced techniques like arrays, loops, and materials.
"""

import json
from supex_driver.adapter.connection import get_sketchup_connection

def main():
    """Create complex 3D models using Ruby scripting"""
    print("Supex Advanced Ruby Modeling Example")
    print("=" * 45)
    
    try:
        # Get connection to SketchUp
        print("Connecting to SketchUp...")
        sketchup = get_sketchup_connection()
        print("✓ Connected to SketchUp")
        
        # Clear scene and create a modern chair design
        print("\nCreating modern chair design with Ruby...")
        chair_code = """
        model = Sketchup.active_model
        entities = model.active_entities
        entities.clear!
        
        # Create chair seat
        seat = entities.add_group
        seat.name = "Chair Seat"
        seat_face = seat.entities.add_face(
          [0, 0, 18.inches], [20.inches, 0, 18.inches],
          [20.inches, 20.inches, 18.inches], [0, 20.inches, 18.inches]
        )
        seat_face.pushpull(2.inches)
        
        # Create chair back
        back = entities.add_group
        back.name = "Chair Back"
        back_face = back.entities.add_face(
          [0, 18.inches, 18.inches], [20.inches, 18.inches, 18.inches],
          [20.inches, 20.inches, 18.inches], [0, 20.inches, 18.inches]
        )
        back_face.pushpull(16.inches)
        
        # Create chair legs using array iteration
        leg_positions = [
          [2.inches, 2.inches, 0],      # Front left
          [18.inches, 2.inches, 0],     # Front right
          [2.inches, 18.inches, 0],     # Back left  
          [18.inches, 18.inches, 0]     # Back right
        ]
        
        leg_positions.each_with_index do |pos, i|
          leg = entities.add_group
          leg.name = "Chair Leg #{i + 1}"
          
          # Create rectangular leg
          leg_face = leg.entities.add_face(
            [pos[0], pos[1], pos[2]],
            [pos[0] + 2.inches, pos[1], pos[2]],
            [pos[0] + 2.inches, pos[1] + 2.inches, pos[2]],
            [pos[0], pos[1] + 2.inches, pos[2]]
          )
          leg_face.pushpull(18.inches)
        end
        
        # Apply modern gray material to all chair parts
        gray_material = model.materials.add("Modern Gray")
        gray_material.color = [74, 74, 74]  # Dark gray
        
        entities.each do |entity|
          entity.material = gray_material if entity.is_a?(Sketchup::Group)
        end
        
        puts "Modern chair created with 4 legs and back"
        """
        
        sketchup.send_command("eval_ruby", {"code": chair_code})
        print("✓ Modern chair created")
        
        # Create a parametric spiral staircase
        print("\nCreating parametric spiral staircase...")
        staircase_code = """
        # Parametric spiral staircase
        steps = 12
        radius = 4.feet
        height_per_step = 8.inches
        step_angle = 360.0 / steps
        
        steps.times do |i|
          step = entities.add_group
          step.name = "Spiral Step #{i + 1}"
          
          # Calculate position and rotation
          angle = (step_angle * i) * Math::PI / 180
          x = radius * Math.cos(angle)
          y = radius * Math.sin(angle)
          z = height_per_step * i
          
          # Create step geometry
          step_width = 3.feet
          step_depth = 12.inches
          step_thickness = 1.5.inches
          
          # Create step face
          step_face = step.entities.add_face(
            [x - step_width/2, y - step_depth/2, z],
            [x + step_width/2, y - step_depth/2, z],
            [x + step_width/2, y + step_depth/2, z],
            [x - step_width/2, y + step_depth/2, z]
          )
          step_face.pushpull(step_thickness)
          
          # Apply wood material
          wood_material = model.materials.add("Oak Wood")
          wood_material.color = [160, 82, 45]  # Saddle brown
          step.material = wood_material
        end
        
        puts "Spiral staircase with #{steps} steps created"
        """
        
        sketchup.send_command("eval_ruby", {"code": staircase_code})
        print("✓ Spiral staircase created")
        
        # Create a bookshelf with books
        print("\nCreating bookshelf with individual books...")
        bookshelf_code = """
        # Create bookshelf frame
        shelf = entities.add_group
        shelf.name = "Bookshelf"
        
        # Bookshelf dimensions
        shelf_width = 3.feet
        shelf_height = 6.feet
        shelf_depth = 12.inches
        
        # Create vertical sides
        2.times do |i|
          side_x = i == 0 ? 8.feet : 8.feet + shelf_width - 1.inches
          side = shelf.entities.add_face(
            [side_x, 0, 0],
            [side_x + 1.inches, 0, 0],
            [side_x + 1.inches, shelf_depth, 0],
            [side_x, shelf_depth, 0]
          )
          side.pushpull(shelf_height)
        end
        
        # Create horizontal shelves
        5.times do |i|
          shelf_y = shelf_height / 4 * i
          shelf_face = shelf.entities.add_face(
            [8.feet, 0, shelf_y],
            [8.feet + shelf_width, 0, shelf_y],
            [8.feet + shelf_width, shelf_depth, shelf_y],
            [8.feet, shelf_depth, shelf_y]
          )
          shelf_face.pushpull(1.inches)
        end
        
        # Apply shelf material
        shelf_material = model.materials.add("Pine Wood")
        shelf_material.color = [222, 184, 135]  # Burlywood
        shelf.material = shelf_material
        
        # Create individual books
        book_colors = [
          [220, 20, 60],    # Crimson
          [50, 205, 50],    # Lime green
          [255, 215, 0],    # Gold
          [70, 130, 180],   # Steel blue
          [255, 69, 0],     # Red orange
          [138, 43, 226]    # Blue violet
        ]
        
        # Add books to different shelves
        4.times do |shelf_level|
          shelf_y = shelf_height / 4 * shelf_level + 1.inches
          
          # Random number of books per shelf
          num_books = 6 + rand(4)  # 6-9 books per shelf
          book_x = 8.feet + 1.inches
          
          num_books.times do |book_i|
            book = entities.add_group
            book.name = "Book #{shelf_level+1}-#{book_i+1}"
            
            # Varying book dimensions
            book_width = 0.5.inches + rand(1.inches)
            book_height = 6.inches + rand(3.inches)
            book_depth = 8.inches + rand(2.inches)
            
            # Create book geometry
            book_face = book.entities.add_face(
              [book_x, 1.inches, shelf_y],
              [book_x + book_width, 1.inches, shelf_y],
              [book_x + book_width, 1.inches + book_depth, shelf_y],
              [book_x, 1.inches + book_depth, shelf_y]
            )
            book_face.pushpull(book_height)
            
            # Apply random color
            color = book_colors[rand(book_colors.length)]
            book_material = model.materials.add("Book Color #{book_i}")
            book_material.color = color
            book.material = book_material
            
            # Move to next book position
            book_x += book_width + 0.1.inches
          end
        end
        
        puts "Bookshelf created with multiple books on each shelf"
        """
        
        sketchup.send_command("eval_ruby", {"code": bookshelf_code})
        print("✓ Bookshelf with books created")
        
        # Create geometric art installation
        print("\nCreating geometric art installation...")
        art_code = """
        # Create geometric art installation
        art = entities.add_group
        art.name = "Geometric Art Installation"
        
        # Create multiple geometric shapes in a pattern
        shapes = [
          { type: :cube, size: 1.feet, color: [255, 0, 0] },
          { type: :sphere, size: 1.feet, color: [0, 255, 0] },
          { type: :pyramid, size: 1.feet, color: [0, 0, 255] },
          { type: :cylinder, size: 1.feet, color: [255, 255, 0] }
        ]
        
        # Create 4x4 grid of shapes
        4.times do |row|
          4.times do |col|
            shape_data = shapes[(row + col) % shapes.length]
            
            shape = art.entities.add_group
            shape.name = "Art Shape #{row}-#{col}"
            
            x = 15.feet + col * 2.5.feet
            y = row * 2.5.feet
            z = 0
            
            case shape_data[:type]
            when :cube
              face = shape.entities.add_face(
                [x, y, z], [x + shape_data[:size], y, z],
                [x + shape_data[:size], y + shape_data[:size], z],
                [x, y + shape_data[:size], z]
              )
              face.pushpull(shape_data[:size])
              
            when :sphere
              # Create simplified sphere with circles
              center = [x + shape_data[:size]/2, y + shape_data[:size]/2, z + shape_data[:size]/2]
              8.times do |i|
                circle = shape.entities.add_circle(center, [1, 0, 0], shape_data[:size]/2, 12)
                circle = shape.entities.add_circle(center, [0, 1, 0], shape_data[:size]/2, 12)
              end
              
            when :pyramid
              base = shape.entities.add_face(
                [x, y, z], [x + shape_data[:size], y, z],
                [x + shape_data[:size], y + shape_data[:size], z],
                [x, y + shape_data[:size], z]
              )
              apex = [x + shape_data[:size]/2, y + shape_data[:size]/2, z + shape_data[:size]]
              base.vertices.each do |vertex|
                shape.entities.add_face(vertex.position, 
                  vertex.position + [shape_data[:size], 0, 0], apex)
              end
              
            when :cylinder
              center = [x + shape_data[:size]/2, y + shape_data[:size]/2, z]
              circle = shape.entities.add_circle(center, [0, 0, 1], shape_data[:size]/2, 16)
              face = shape.entities.add_face(circle)
              face.pushpull(shape_data[:size])
            end
            
            # Apply color
            shape_material = model.materials.add("Art Color #{row}-#{col}")
            shape_material.color = shape_data[:color]
            shape.material = shape_material
          end
        end
        
        puts "Geometric art installation created with 16 shapes"
        """
        
        sketchup.send_command("eval_ruby", {"code": art_code})
        print("✓ Geometric art installation created")
        
        # Summary
        print("\n" + "=" * 45)
        print("✓ Advanced Ruby modeling example completed!")
        print("Created using pure SketchUp Ruby API:")
        print("  • Modern chair with precise measurements")
        print("  • Parametric spiral staircase (12 steps)")
        print("  • Bookshelf with randomly generated books")
        print("  • Geometric art installation (16 shapes)")
        print("  • Multiple materials and organized groups")
        print("  • Advanced Ruby techniques: loops, arrays, randomization")
        print("\n🎯 All geometry created via eval_ruby - unlimited flexibility!")
        
        # Optionally export the scene
        export_choice = input("\nWould you like to export the scene? (y/N): ")
        if export_choice.lower() == 'y':
            print("Exporting scene as SKP file...")
            export_result = sketchup.send_command(
                "export_scene", 
                {"format": "skp"}
            )
            print(f"✓ Scene exported")
        
    except Exception as e:
        print(f"✗ Error: {e}")
        print("Make sure SketchUp is running and the SUP-MCP extension is started.")

if __name__ == "__main__":
    main()