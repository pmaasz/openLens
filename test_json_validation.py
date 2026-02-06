#!/usr/bin/env python3
"""
Test JSON schema validation functionality
"""

import json
import tempfile
import os
from pathlib import Path

# Import validation functions
from src.validation import (
    validate_lens_data_schema,
    validate_lenses_json_schema,
    ValidationError
)
from src.lens_editor import Lens, LensManager

def test_valid_lens_schema():
    """Test that valid lens data passes validation"""
    print("Testing valid lens schema...")
    
    valid_data = {
        'name': 'Test Lens',
        'radius_of_curvature_1': 100.0,
        'radius_of_curvature_2': -100.0,
        'thickness': 5.0,
        'diameter': 50.0,
        'refractive_index': 1.5168,
        'type': 'Biconvex',
        'material': 'BK7'
    }
    
    try:
        validated = validate_lens_data_schema(valid_data)
        print("✓ Valid lens data passed validation")
        return True
    except ValidationError as e:
        print(f"✗ Valid lens data failed validation: {e}")
        return False


def test_missing_required_field():
    """Test that missing required fields are caught"""
    print("\nTesting missing required field detection...")
    
    invalid_data = {
        'name': 'Test Lens',
        # Missing radius_of_curvature_1
        'radius_of_curvature_2': -100.0,
        'thickness': 5.0,
        'diameter': 50.0,
        'refractive_index': 1.5168
    }
    
    try:
        validate_lens_data_schema(invalid_data)
        print("✗ Missing required field was not detected")
        return False
    except ValidationError as e:
        print(f"✓ Missing required field caught: {e}")
        return True


def test_wrong_type():
    """Test that wrong types are caught"""
    print("\nTesting wrong type detection...")
    
    invalid_data = {
        'name': 'Test Lens',
        'radius_of_curvature_1': "not a number",  # Should be float
        'radius_of_curvature_2': -100.0,
        'thickness': 5.0,
        'diameter': 50.0,
        'refractive_index': 1.5168
    }
    
    try:
        validate_lens_data_schema(invalid_data)
        print("✗ Wrong type was not detected")
        return False
    except ValidationError as e:
        print(f"✓ Wrong type caught: {e}")
        return True


def test_not_dict():
    """Test that non-dict data is rejected"""
    print("\nTesting non-dict data rejection...")
    
    invalid_data = "not a dictionary"
    
    try:
        validate_lens_data_schema(invalid_data)
        print("✗ Non-dict data was not rejected")
        return False
    except ValidationError as e:
        print(f"✓ Non-dict data rejected: {e}")
        return True


def test_valid_lenses_array():
    """Test that valid lenses array passes validation"""
    print("\nTesting valid lenses array...")
    
    valid_array = [
        {
            'name': 'Lens 1',
            'radius_of_curvature_1': 100.0,
            'radius_of_curvature_2': -100.0,
            'thickness': 5.0,
            'diameter': 50.0,
            'refractive_index': 1.5168
        },
        {
            'name': 'Lens 2',
            'radius_of_curvature_1': 200.0,
            'radius_of_curvature_2': -200.0,
            'thickness': 3.0,
            'diameter': 25.0,
            'refractive_index': 1.6
        }
    ]
    
    try:
        validated = validate_lenses_json_schema(valid_array)
        print(f"✓ Valid lenses array passed validation ({len(validated)} lenses)")
        return True
    except ValidationError as e:
        print(f"✗ Valid lenses array failed validation: {e}")
        return False


def test_not_array():
    """Test that non-array root is rejected"""
    print("\nTesting non-array root rejection...")
    
    invalid_data = {'not': 'an array'}
    
    try:
        validate_lenses_json_schema(invalid_data)
        print("✗ Non-array root was not rejected")
        return False
    except ValidationError as e:
        print(f"✓ Non-array root rejected: {e}")
        return True


def test_lens_manager_with_invalid_json():
    """Test that LensManager handles invalid JSON gracefully"""
    print("\nTesting LensManager with invalid JSON...")
    
    # Create temporary file with invalid JSON
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        temp_file = f.name
        # Write invalid schema (not an array)
        json.dump({'invalid': 'schema'}, f)
    
    try:
        manager = LensManager(storage_file=temp_file)
        lenses = manager.load_lenses()
        
        if len(lenses) == 0:
            print("✓ LensManager correctly returned empty list for invalid schema")
            return True
        else:
            print(f"✗ LensManager returned {len(lenses)} lenses from invalid schema")
            return False
    finally:
        os.unlink(temp_file)


def test_lens_manager_with_malformed_lens():
    """Test that LensManager handles malformed lens data gracefully"""
    print("\nTesting LensManager with malformed lens...")
    
    # Create temporary file with array containing invalid lens
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        temp_file = f.name
        json.dump([
            {
                'name': 'Good Lens',
                'radius_of_curvature_1': 100.0,
                'radius_of_curvature_2': -100.0,
                'thickness': 5.0,
                'diameter': 50.0,
                'refractive_index': 1.5168
            },
            {
                'name': 'Bad Lens',
                # Missing required fields
                'thickness': 5.0
            }
        ], f)
    
    try:
        manager = LensManager(storage_file=temp_file)
        lenses = manager.load_lenses()
        
        if len(lenses) == 0:
            print("✓ LensManager correctly rejected array with malformed lens")
            return True
        else:
            print(f"✗ LensManager loaded {len(lenses)} lenses from malformed array")
            return False
    finally:
        os.unlink(temp_file)


def test_lens_manager_with_valid_json():
    """Test that LensManager works with valid JSON"""
    print("\nTesting LensManager with valid JSON...")
    
    # Create temporary file with valid JSON
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        temp_file = f.name
        json.dump([
            {
                'name': 'Test Lens 1',
                'radius_of_curvature_1': 100.0,
                'radius_of_curvature_2': -100.0,
                'thickness': 5.0,
                'diameter': 50.0,
                'refractive_index': 1.5168,
                'type': 'Biconvex',
                'material': 'BK7'
            }
        ], f)
    
    try:
        manager = LensManager(storage_file=temp_file)
        lenses = manager.load_lenses()
        
        if len(lenses) == 1 and lenses[0].name == 'Test Lens 1':
            print(f"✓ LensManager successfully loaded valid lens: {lenses[0].name}")
            return True
        else:
            print(f"✗ LensManager failed to load valid lens correctly")
            return False
    finally:
        os.unlink(temp_file)


def main():
    """Run all tests"""
    print("=" * 60)
    print("JSON Schema Validation Tests")
    print("=" * 60)
    
    tests = [
        test_valid_lens_schema,
        test_missing_required_field,
        test_wrong_type,
        test_not_dict,
        test_valid_lenses_array,
        test_not_array,
        test_lens_manager_with_invalid_json,
        test_lens_manager_with_malformed_lens,
        test_lens_manager_with_valid_json
    ]
    
    results = []
    for test in tests:
        try:
            results.append(test())
        except Exception as e:
            print(f"✗ Test crashed with exception: {e}")
            import traceback
            traceback.print_exc()
            results.append(False)
    
    print("\n" + "=" * 60)
    print(f"Results: {sum(results)}/{len(results)} tests passed")
    print("=" * 60)
    
    return all(results)


if __name__ == '__main__':
    success = main()
    exit(0 if success else 1)
