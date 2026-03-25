import os
import sys

# Mocking Odoo context for testing logic
import math

class MockRecord:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)

def test_ceil_logic():
    # Test: 73kg required, 12kg per unit
    qty_kg = 73.0
    weight = 12.0
    qty_unit = math.ceil(qty_kg / weight)
    print(f"Test 1: {qty_kg}kg / {weight}kg per unit = {qty_unit} units (Expected 7)")
    assert qty_unit == 7

    # Test: 120kg required, 10kg per unit
    qty_kg = 120.0
    weight = 10.0
    qty_unit = math.ceil(qty_kg / weight)
    print(f"Test 2: {qty_kg}kg / {weight}kg per unit = {qty_unit} units (Expected 12)")
    assert qty_unit == 12

    # Test: 10.1kg required, 10kg per unit
    qty_kg = 10.1
    weight = 10.0
    qty_unit = math.ceil(qty_kg / weight)
    print(f"Test 3: {qty_kg}kg / {weight}kg per unit = {qty_unit} units (Expected 2)")
    assert qty_unit == 2

if __name__ == "__main__":
    try:
        test_ceil_logic()
        print("Logic Verification Passed!")
    except Exception as e:
        print(f"Logic Verification Failed: {e}")
        sys.exit(1)
