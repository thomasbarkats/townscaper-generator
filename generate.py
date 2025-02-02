import base64
import json
import math
import random
import time
import os
from dotenv import load_dotenv
import xml.etree.ElementTree as ET
from xml.dom import minidom
from typing import List, Set, Tuple

# Style parameter ranges (min, max)
PARAM_RANGES = {
    'max_height': (6, 10),              # Integer: Maximum building height - affects city skyline and zone calculation
    'street_density': (1.2, 1.6),       # Float: Higher value = more compact street grid, lower = more spread out streets
    'landmark_freq': (0.1, 0.4),        # Float: Probability (0-1) of a building being taller as a landmark
    'town_size': (100, 150)             # Integer: Maximum radius of the city in map units, limited by base terrain
}

COLOR_PALETTES = {
    'terracotta': [0, 1, 11, 12, 13],    # Warm, earthy tones
    'pastel': [1, 2, 8, 13, 14],         # Soft, light tones
    'nature': [3, 4, 6, 7, 12],          # Green, natural tones
    'mediterranean': [8, 9, 13, 14, 1],  # Blue and white tones
    'urban': [10, 11, 12, 13, 14],       # Sober, urban tones
    'traditional': [11, 12, 13, 1, 0]    # Traditional tones
}

# Load environment variables
load_dotenv(override=True)
OUTPUT_PATH = os.getenv('GAME_PATH', 'towns')

# Create towns directory if running locally
if OUTPUT_PATH == 'towns' and not os.path.exists(OUTPUT_PATH):
    os.makedirs(OUTPUT_PATH)

class CityGenerator:
    # Thematic color palettes for different city styles

    def __init__(self, valid_coords_file: str = "bases/map.json"):
        with open(valid_coords_file, 'r') as f:
            self.valid_coords = json.load(f)

        # Generate random values within defined ranges
        self.style_params = {
            'max_height': random.randint(
                PARAM_RANGES['max_height'][0], 
                PARAM_RANGES['max_height'][1]),
            'street_density': random.uniform(
                PARAM_RANGES['street_density'][0],
                PARAM_RANGES['street_density'][1]),
            'landmark_freq': random.uniform(
                PARAM_RANGES['landmark_freq'][0],
                PARAM_RANGES['landmark_freq'][1]),
            'town_size': random.randint(
                PARAM_RANGES['town_size'][0],
                PARAM_RANGES['town_size'][1]),
            'color_palette': random.choice(list(COLOR_PALETTES.values()))
        }

    def _get_zone_type(self, x: int, y: int, center_x: int, center_y: int) -> str:
        """Determines zone type based on distance from city center"""
        dist = math.sqrt((x - center_x)**2 + (y - center_y)**2)
        dist_ratio = dist / self.style_params['max_height']
        return 'historic' if dist_ratio < 0.4 else 'residential'

    def _select_map_region(self, center_x: float = None, center_y: float = None) -> List[dict]:
        """Selects a connected region from the map around specified or calculated center"""
        if center_x is None:
            center_x = sum(c['x'] for c in self.valid_coords) / len(self.valid_coords)
        if center_y is None:
            center_y = sum(c['y'] for c in self.valid_coords) / len(self.valid_coords)

        return [coord for coord in self.valid_coords 
                if math.sqrt((coord['x'] - center_x)**2 + (coord['y'] - center_y)**2) <= self.style_params['town_size']]

    def _add_street_segment(self, coords: List[dict], street_coords: Set[Tuple[int, int]], 
                          start_x: int, start_y: int, angle: float, length: int, grid_size: int) -> List[Tuple[int, int]]:
        """Creates a street segment in the specified direction, finding valid coordinates"""
        current_x, current_y = start_x, start_y
        segment = []

        for _ in range(length):
            target_x = current_x + math.cos(angle) * grid_size
            target_y = current_y + math.sin(angle) * grid_size

            # Find nearest valid point for street placement
            nearest = min(
                (c for c in coords if (c['x'], c['y']) not in street_coords),
                key=lambda c: math.sqrt((c['x'] - target_x)**2 + (c['y'] - target_y)**2),
                default=None
            )

            if nearest and math.sqrt((nearest['x'] - target_x)**2 + (nearest['y'] - target_y)**2) < grid_size * 1.5:
                pos = (nearest['x'], nearest['y'])
                street_coords.add(pos)
                segment.append(pos)
                current_x, current_y = nearest['x'], nearest['y']
            else:
                break

        return segment

    def _create_street_network(self, coords: List[dict], center_x: int, center_y: int) -> Set[Tuple[int, int]]:
        """Creates a connected street network with main streets and perpendicular side streets"""
        street_coords = set()
        grid_size = int(12 / self.style_params['street_density'])

        # Create main streets from center in cardinal directions
        for angle in [0, math.pi/2, math.pi, 3*math.pi/2]:
            main_segment = self._add_street_segment(coords, street_coords, center_x, center_y, angle, 25, grid_size)

            # Add perpendicular streets off main streets
            if main_segment:
                for i in range(1, len(main_segment) - 1, 3):
                    if random.random() < 0.7:  # 70% chance for perpendicular street
                        x, y = main_segment[i]
                        self._add_street_segment(coords, street_coords, x, y, angle + math.pi/2, 10, grid_size)

        return street_coords

    def _generate_buildings(self, coords: List[dict], center_x: int, center_y: int) -> List[dict]:
        """Generates buildings with streets, considering zone types and landmarks"""
        buildings = []
        used_coords = set()
        street_coords = self._create_street_network(coords, center_x, center_y)

        # Add streets
        for x, y in street_coords:
            used_coords.add((x, y))
            buildings.append({
                'blocks': [{'x': x, 'y': y}],
                'height': 1,
                'color': 15,
                'type': 'street'
            })

        # Create buildings
        for coord in coords:
            if (coord['x'], coord['y']) in used_coords:
                continue

            zone_type = self._get_zone_type(coord['x'], coord['y'], center_x, center_y)
            is_landmark = random.random() < self.style_params['landmark_freq']

            height = random.randint(3, 5) if zone_type == 'historic' else random.randint(2, 4)
            if is_landmark:
                height += random.randint(1, 2)

            buildings.append({
                'blocks': [coord],
                'height': height,
                'color': random.choice(self.style_params['color_palette']),
                'type': zone_type
            })
            used_coords.add((coord['x'], coord['y']))

        return buildings

    def generate_city(self, center_x: float = None, center_y: float = None) -> Tuple[List[dict], List[dict]]:
        """Generates complete city structure including buildings and layout"""
        selected_coords = self._select_map_region(center_x, center_y)
        
        if not center_x or not center_y:
            center_x = sum(c['x'] for c in selected_coords) / len(selected_coords)
            center_y = sum(c['y'] for c in selected_coords) / len(selected_coords)

        buildings = self._generate_buildings(selected_coords, center_x, center_y)

        # Convert to game format
        corners = [
            {'x': block['x'], 'y': block['y'], 'count': building['height']}
            for building in buildings
            for block in building['blocks']
        ]

        voxels = [
            {'t': 15 if h == 0 else building['color'], 'h': h}
            for building in buildings
            for _ in building['blocks']
            for h in range(building['height'])
        ]

        return corners, voxels

    def create_scape_file(self, output_file: str = None, center_x: float = None, center_y: float = None):
        """Creates the game save file in the required XML format"""
        if output_file is None:
            filename = f'GeneratedTown_{math.floor(time.time())}.scape'
            output_file = os.path.normpath(os.path.join(OUTPUT_PATH, filename))

        corners, voxels = self.generate_city(center_x, center_y)

        params_str = "Generation parameters:"
        for param, value in self.style_params.items():
            if param == 'color_palette':
                params_str += f"\n - {param}: {value}"
            else:
                params_str += f"\n - {param}: {value:.2f}" if isinstance(value, float) else f"\n - {param}: {value}"
        print(params_str)

        root = ET.Element('SaveData')
        root.set('xmlns:xsd', 'http://www.w3.org/2001/XMLSchema')
        root.set('xmlns:xsi', 'http://www.w3.org/2001/XMLSchema-instance')

        # Add generation parameters as XML comment (will be removed once opened in game!)
        root.append(ET.Comment(params_str))

        # Add camera position
        cam = ET.SubElement(root, 'cam')
        ET.SubElement(cam, 'x').text = str(int(center_x or 0))
        ET.SubElement(cam, 'y').text = str(int(center_y or 0))
        ET.SubElement(cam, 'z').text = '78'

        # Add sun settings
        sun = ET.SubElement(root, 'sun')
        ET.SubElement(sun, 'h').text = str(random.randint(80, 170))  # height
        ET.SubElement(sun, 'r').text = str(random.randint(80, 170))  # rotation

        # Add corners data
        corners_elem = ET.SubElement(root, 'corners')
        for corner in corners:
            c = ET.SubElement(corners_elem, 'C')
            ET.SubElement(c, 'x').text = str(corner['x'])
            ET.SubElement(c, 'y').text = str(corner['y'])
            ET.SubElement(c, 'count').text = str(corner['count'])

        # Add voxels data
        voxels_elem = ET.SubElement(root, 'voxels')
        for voxel in voxels:
            v = ET.SubElement(voxels_elem, 'V')
            ET.SubElement(v, 't').text = str(voxel['t'])
            ET.SubElement(v, 'h').text = str(voxel['h'])

        # Add temporary thumbnail (will be overwritten once opened in game)
        with open("assets/image.jpg", "rb") as image_file:
            encoded_image = base64.b64encode(image_file.read()).decode('utf-8')
            bigJpg = ET.SubElement(root, 'bigJpg')
            bigJpg.text = encoded_image

        # Save formatted XML
        xml_str = minidom.parseString(ET.tostring(root)).toprettyxml(indent="  ")
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(xml_str)

if __name__ == "__main__":
    generator = CityGenerator()  # Uses local map.json
    generator.create_scape_file()  # Saves to configured directory