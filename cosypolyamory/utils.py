"""
Utility functions for cosypolyamory.org

Common helper functions used across the application.
"""

import re
import urllib.parse


def extract_google_maps_info(maps_url):
    """Extract coordinates or place information from Google Maps URL"""
    if not maps_url:
        return None
    
    try:
        # If it's a short URL, resolve it first
        if 'goo.gl' in maps_url or 'maps.app.goo.gl' in maps_url:
            try:
                import urllib.request as url_request
                req = url_request.Request(maps_url)
                req.add_header('User-Agent', 'Mozilla/5.0 (compatible; bot)')
                with url_request.urlopen(req) as response:
                    maps_url = response.geturl()
                    print(f"Resolved short URL to: {maps_url}")
            except Exception as e:
                print(f"Could not resolve short URL: {e}")
                # Fall back to search mode if resolution fails
                return {'search_url': maps_url}
        
        # Try to extract coordinates from various Google Maps URL formats
        # Format 1: /@lat,lng,zoom
        coord_pattern = r'/@(-?\d+\.?\d*),(-?\d+\.?\d*),\d+\.?\d*z'
        coord_match = re.search(coord_pattern, maps_url)
        if coord_match:
            lat, lng = coord_match.groups()
            return {'lat': float(lat), 'lng': float(lng)}
        
        # Format 2: /place/Name/@lat,lng
        place_coord_pattern = r'/place/[^/@]+/@(-?\d+\.?\d*),(-?\d+\.?\d*)'
        place_coord_match = re.search(place_coord_pattern, maps_url)
        if place_coord_match:
            lat, lng = place_coord_match.groups()
            return {'lat': float(lat), 'lng': float(lng)}
        
        # Format 3: URL parameters like 3d41.381138!4d2.186112
        param_coord_pattern = r'3d(-?\d+\.?\d*)!4d(-?\d+\.?\d*)'
        param_coord_match = re.search(param_coord_pattern, maps_url)
        if param_coord_match:
            lat, lng = param_coord_match.groups()
            return {'lat': float(lat), 'lng': float(lng)}
        
        # Format 4: Extract place ID for places
        place_id_pattern = r'place/([^/@?]+)'
        place_match = re.search(place_id_pattern, maps_url)
        if place_match:
            place_name = urllib.parse.unquote(place_match.group(1)).replace('+', ' ')
            return {'place_name': place_name}
            
        # Format 5: Query parameter format ?q=location
        query_pattern = r'[?&]q=([^&]+)'
        query_match = re.search(query_pattern, maps_url)
        if query_match:
            place_name = urllib.parse.unquote(query_match.group(1)).replace('+', ' ')
            return {'place_name': place_name}
            
    except Exception as e:
        print(f"Error parsing Google Maps URL: {e}")
    
    return None
