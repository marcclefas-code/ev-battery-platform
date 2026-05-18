import pytest
from app.models.property_definition import PropertyDefinition


class TestPropertyDefinitionModel:
    def test_property_definition_fields(self):
        prop = PropertyDefinition(
            code='nominal_voltage',
            label='Nominal Voltage',
            unit='V',
            data_type='number',
            applies_to=['pack', 'hv_module'],
            category='electrical',
        )
        assert prop.code == 'nominal_voltage'
        assert prop.unit == 'V'
        assert 'pack' in prop.applies_to
