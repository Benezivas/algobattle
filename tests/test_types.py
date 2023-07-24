"""Tests for pydantic parsing types."""
from typing import Annotated
from unittest import TestCase, main

from pydantic import ValidationError

from algobattle.problem import InstanceModel, AttributeReference, SelfRef
from algobattle.types import Ge, Interval, SizeIndex, UniqueItems


class ModelCreationTests(TestCase):
    """Test that the model creation process runs smoothly."""

    def test_basic(self):
        basic_instance()

    def test_size(self):
        size_instance()

    def test_interval(self):
        interval_instance()

    def test_uniqe(self):
        unique_items_instance()


def basic_instance() -> type[InstanceModel]:
    """Create a basic instance class."""

    class TestModel(InstanceModel):
        ge_const: Annotated[int, Ge(0)]
        ge_ref: Annotated[int, Ge(AttributeReference("self", "ge_const"))]

        @property
        def size(self) -> int:
            return 0

    return TestModel


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

    def test_wrong_ref_context(self):
        """Reject a wrong instance."""
        with self.assertRaises(ValidationError):
            self.TestModel.model_validate(self.wrong_ref_instance_dict)


def size_instance() -> type[InstanceModel]:
    """Create a basic solution class."""

    class SizeModel(InstanceModel):
        items: list[int]
        index: SizeIndex

        @property
        def size(self) -> int:
            return len(self.items)

    return SizeModel


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
        with self.assertRaises(ValidationError):
            self.TestModel.model_validate({"items": [1, 2], "index": 2})


def interval_instance() -> type[InstanceModel]:
    """Create a basic solution class with an Interval constraint."""

    class IntervalModel(InstanceModel):
        lower_bound: int
        i: Annotated[int, Interval(ge=SelfRef.lower_bound, lt=10)]

        @property
        def size(self) -> int:
            return self.i

    return IntervalModel


class IntervalTests(TestCase):
    """Tests for the Interval grouped metada."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.TestModel = interval_instance()

    def test_accept(self):
        """Accept correct instance."""
        self.TestModel.model_validate({"lower_bound": 0, "i": 5})

    def test_reject_lower(self):
        """Reject instance incorrect because of lower bound."""
        with self.assertRaises(ValidationError):
            self.TestModel.model_validate({"lower_bound": 0, "i": -1})

    def test_reject_upper(self):
        """Reject instance incorrect because of upper bound."""
        model_dict = {"lower_bound": 0, "i": 10}
        with self.assertRaises(ValidationError):
            self.TestModel.model_validate(model_dict)


def unique_items_instance() -> type[InstanceModel]:
    """Create a basic instance class with a unique items constraint."""

    class UniqueModel(InstanceModel):
        array: Annotated[list[int], UniqueItems]

        @property
        def size(self) -> int:
            return len(self.array)

    return UniqueModel


class UniqueItemsTest(TestCase):
    """Tests for the unique items decorator."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.TestModel = unique_items_instance()

    def test_success(self):
        self.TestModel.model_validate({"array": [1, 2, 3]})

    def test_rejected(self):
        with self.assertRaises(ValidationError):
            self.TestModel.model_validate({"array": [1, 2, 2]})

    def test_schema(self):
        schema = self.TestModel.model_json_schema()
        self.assertIn("uniqueItems", schema["properties"]["array"])


if __name__ == "__main__":
    main()
