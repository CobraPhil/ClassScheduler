#!/usr/bin/env python3
"""
Simple test script to verify the class color generation functionality.
"""

import colorsys

def generate_class_colors(class_names):
    """Generate distinctive colors for each class using HSL color space with improved distribution"""
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
        
        # Vary saturation more dramatically to increase distinction
        saturation = 0.70 + (i % 6) * 0.05  # 0.70-0.95 range (broader range)
        
        # Use darker lightness values with more variation
        lightness = 0.28 + (i % 7) * 0.025  # 0.28-0.43 range (more variation)
        
        # Convert HSL to RGB
        r, g, b = colorsys.hls_to_rgb(h, lightness, saturation)
        
        # Convert to hex color
        hex_color = '#{:02x}{:02x}{:02x}'.format(
            int(r * 255),
            int(g * 255), 
            int(b * 255)
        )
        
        colors[class_name] = hex_color
    
    return colors

def test_color_generation():
    """Test the color generation with various class lists"""
    
    print("Testing Class Color Generation")
    print("=" * 50)
    
    # Test with small number of classes
    small_classes = ['Math 101', 'English 102', 'History 103', 'Science 104']
    colors_small = generate_class_colors(small_classes)
    
    print(f"\nSmall class list ({len(small_classes)} classes):")
    for class_name, color in colors_small.items():
        print(f"  {class_name:<15} -> {color}")
    
    # Test with larger number of classes (simulating the 25 class scenario)
    large_classes = [
        'GECO 101', 'GELA 102', 'THEO 201', 'BIBL 301', 'HIST 401',
        'PHIL 201', 'COMM 301', 'PSYC 201', 'SOCI 301', 'MATH 101',
        'ENGL 102', 'SPAN 201', 'FREN 201', 'GERM 201', 'ITAL 201',
        'CHEM 301', 'BIOL 201', 'PHYS 301', 'GEOL 201', 'ASTR 301',
        'MUSC 101', 'ART 201', 'DRAM 301', 'DANC 201', 'FILM 301'
    ]
    colors_large = generate_class_colors(large_classes)
    
    print(f"\nLarge class list ({len(large_classes)} classes):")
    for class_name, color in colors_large.items():
        print(f"  {class_name:<15} -> {color}")
    
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