import pytest

from cq3d.errors import ValidationError
from cq3d.parser import parse_document
from cq3d.validator import validate_document


def test_rejects_variable_reassignment():
    document = parse_document(
        """
model demo
unit mm
width = 10
width = 20
"""
    )
    with pytest.raises(ValidationError, match="cannot be reassigned"):
        validate_document(document)


def test_rejects_unknown_object_reference():
    document = parse_document(
        """
model demo
unit mm

box base
  size 10 10 10
end

combine body
  union base missing
end
"""
    )
    with pytest.raises(ValidationError, match="unknown object 'missing'"):
        validate_document(document)


def test_requires_positive_dimensions():
    document = parse_document(
        """
model demo
unit mm

box base
  size 10 0 10
end
"""
    )
    with pytest.raises(ValidationError, match="dimensions must be greater than zero"):
        validate_document(document)
