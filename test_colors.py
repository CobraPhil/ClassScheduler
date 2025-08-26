#!/usr/bin/env python3
"""
Simple test script to verify the class color generation functionality.
"""

import colorsys

def generate_class_colors(class_names):
    """Generate two-tone colors for each class - header and body colors for enhanced distinction"""
    colors = {}
    
    if not class_names:
        return colors
    
    num_classes = len(class_names)
    
    # Sort class names for consistent color assignment
    sorted_classes = sorted(class_names)
    
    # Use golden ratio for better color distribution (avoids clustering)
    golden_ratio = 0.618033988749
    
    for i, class_name in enumerate(sorted_classes):
        # Use golden ratio to distribute hues more evenly across spectrum
        # This prevents similar colors from clustering together
        hue = (i * golden_ratio * 360.0) % 360
        
        # Add cyclic variations based on position to ensure diversity
        cycle_variation = (i % 7) * 8  # 0, 8, 16, 24, 32, 40, 48 degree shifts
        hue = (hue + cycle_variation) % 360
        
        # Convert hue to 0-1 range for colorsys
        h = hue / 360.0
        
        # Generate TWO related colors for two-tone effect
        
        # Header color (darker, more saturated for class name)
        header_saturation = 0.75 + (i % 5) * 0.04  # 0.75-0.91 range
        header_lightness = 0.25 + (i % 6) * 0.02   # 0.25-0.35 range (darker)
        
        # Body color (lighter but still dark enough for white text)
        body_saturation = 0.65 + (i % 5) * 0.04    # 0.65-0.81 range (less saturated)
        body_lightness = 0.35 + (i % 6) * 0.02     # 0.35-0.45 range (lighter than header)
        
        # Convert header color
        r1, g1, b1 = colorsys.hls_to_rgb(h, header_lightness, header_saturation)
        header_color = '#{:02x}{:02x}{:02x}'.format(
            int(r1 * 255), int(g1 * 255), int(b1 * 255)
        )
        
        # Convert body color
        r2, g2, b2 = colorsys.hls_to_rgb(h, body_lightness, body_saturation)
        body_color = '#{:02x}{:02x}{:02x}'.format(
            int(r2 * 255), int(g2 * 255), int(b2 * 255)
        )
        
        # Store both colors
        colors[class_name] = {
            'header': header_color,
            'body': body_color,
            'primary': header_color  # For backward compatibility
        }
    
    return colors

def test_color_generation():
    """Test the color generation with various class lists"""
    
    print("Testing Class Color Generation")
    print("=" * 50)
    
    # Test with small number of classes
    small_classes = ['Math 101', 'English 102', 'History 103', 'Science 104']
    colors_small = generate_class_colors(small_classes)
    
    print(f"\nSmall class list ({len(small_classes)} classes):")
    for class_name, color_data in colors_small.items():
        print(f"  {class_name:<15} -> Header: {color_data['header']} | Body: {color_data['body']}")
    
    # Test with larger number of classes (simulating the 25 class scenario)
    large_classes = [
        'GECO 101', 'GELA 102', 'THEO 201', 'BIBL 301', 'HIST 401',
        'PHIL 201', 'COMM 301', 'PSYC 201', 'SOCI 301', 'MATH 101',
        'ENGL 102', 'SPAN 201', 'FREN 201', 'GERM 201', 'ITAL 201',
        'CHEM 301', 'BIOL 201', 'PHYS 301', 'GEOL 201', 'ASTR 301',
        'MUSC 101', 'ART 201', 'DRAM 301', 'DANC 201', 'FILM 301'
    ]
    colors_large = generate_class_colors(large_classes)
    
    print(f"\nLarge class list ({len(large_classes)} classes) - Two-Tone Colors:")
    for class_name, color_data in colors_large.items():
        print(f"  {class_name:<15} -> Header: {color_data['header']} | Body: {color_data['body']}")
    
    # Test color consistency (same input should produce same colors)
    colors_test1 = generate_class_colors(['Class A', 'Class B', 'Class C'])
    colors_test2 = generate_class_colors(['Class A', 'Class B', 'Class C'])
    
    print(f"\nConsistency Test:")
    print("First generation:", colors_test1)
    print("Second generation:", colors_test2)
    print("Colors are consistent:", colors_test1 == colors_test2)
    
    # Test with different order (should still be consistent due to sorting)
    colors_ordered1 = generate_class_colors(['Class A', 'Class B', 'Class C'])
    colors_ordered2 = generate_class_colors(['Class C', 'Class A', 'Class B'])
    
    print(f"\nOrder Independence Test:")
    print("Ordered [A,B,C]:", colors_ordered1)
    print("Ordered [C,A,B]:", colors_ordered2)
    print("Order independent:", colors_ordered1 == colors_ordered2)
    
    print(f"\nColor Analysis:")
    print(f"All colors are darker (good for white text): ", end="")
    # Check if all colors have low lightness values (dark enough for white text)
    all_dark = True
    for hex_color in colors_large.values():
        # Convert hex back to RGB and then to HSL to check lightness
        r = int(hex_color[1:3], 16) / 255.0
        g = int(hex_color[3:5], 16) / 255.0  
        b = int(hex_color[5:7], 16) / 255.0
        h, l, s = colorsys.rgb_to_hls(r, g, b)
        if l > 0.5:  # If lightness > 50%, it might be too light for white text
            all_dark = False
            break
    print("✓" if all_dark else "✗")

if __name__ == "__main__":
    test_color_generation()