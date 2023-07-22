"""Tests for pydantic parsing types."""
from typing import Annotated
from unittest import TestCase, main

from pydantic import ValidationError

from algobattle.problem import InstanceModel
from algobattle.util import SelfReference
from algobattle.types import Ge, SizeIndex


def basic_instance() -> type[InstanceModel]:
    """Create a basic instance class."""

    class TestModel(InstanceModel):
        ge_const: Annotated[int, Ge(0)]
        ge_ref: Annotated[int, Ge(SelfReference("ge_const"))]

        @property
        def size(self) -> int:
            return 0

    return TestModel


def size_instance() -> type[InstanceModel]:
    """Create a basic solution class."""

    class SizeModel(InstanceModel):
        items: list[int]
        index: SizeIndex

        @property
        def size(self) -> int:
            return len(self.items)

    return SizeModel


class ModelCreationTests(TestCase):
    """Test that the model creation process runs smoothly."""

    def test_basic(self):
        basic_instance()

    def test_size(self):
        size_instance()


class BasicTests(TestCase):
    """Tests for the basic attribute ref based features."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.TestModel = basic_instance()
        cls.wrong_ref_instance_dict = {"ge_const": 0, "ge_ref": -1}

    def test_success(self):
        """Successfully validate a correct instance."""
        self.TestModel.model_validate({"ge_const": 0, "ge_ref": 0})

    def test_wrong_const(self):
        """Reject wrong constant comparison."""
        with self.assertRaises(ValidationError, msg="Constant comparison not rejected"):
            self.TestModel.model_validate({"ge_const": -1, "ge_ref": 0})

    def test_wrong_ref_no_context(self):
        """Accept a wrong instance if there is no context passed."""
        self.TestModel.model_validate(self.wrong_ref_instance_dict)

    def test_wrong_ref_context(self):
        """Reject a wrong instance if the context has been set."""
        instance = self.TestModel.model_validate(self.wrong_ref_instance_dict)
        with self.assertRaises(ValidationError, msg="Attr ref comparison not rejectect"):
            self.TestModel.model_validate(self.wrong_ref_instance_dict, context={"self": instance})


class SizeTests(TestCase):
    """Tests for the SizeIndex type."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.TestModel = size_instance()

    def test_success(self):
        """Successfully validate a correct instance."""
        self.TestModel.model_validate({"items": [1, 2, 3], "index": 1})

    def test_index_negative(self):
        """Reject negative indices immedietly."""
        with self.assertRaises(ValidationError):
            self.TestModel.model_validate({"items": [], "index": -1})

    def test_index_large(self):
        """Reject too large indices."""
        model_dict = {"items": [1, 2], "index": 2}
        instance = self.TestModel.model_validate(model_dict)
        with self.assertRaises(ValidationError):
            self.TestModel.model_validate(model_dict, context={"instance": instance})


if __name__ == "__main__":
    main()
