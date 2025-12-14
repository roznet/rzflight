"""
Queryable collection classes for fluent, composable queries.

This module provides a lightweight alternative to query builders that leverages
Python's functional programming capabilities for clean, chainable queries on
in-memory data.
"""

from typing import TypeVar, Generic, Callable, List, Dict, Optional, Any, Union
from collections.abc import Iterable

T = TypeVar('T')


class QueryableCollection(Generic[T]):
    """
    A lightweight, chainable collection for filtering and querying in-memory data.

    Inspired by LINQ, pandas, and Django ORM, but optimized for in-memory use
    with minimal overhead. Supports method chaining, functional filtering,
    and convenient result transformations.

    Examples:
        # Basic filtering
        collection.filter(lambda x: x.value > 10).all()

        # Attribute matching
        collection.where(status='active').all()

        # Chaining
        collection.filter(lambda x: x.value > 10).where(status='active').first()

        # Grouping
        collection.group_by(lambda x: x.category)

        # Sorting
        collection.order_by(lambda x: x.created_at, reverse=True).take(10).all()
    """

    def __init__(self, items: Union[List[T], Iterable[T]]):
        """
        Initialize a queryable collection.

        Args:
            items: List or iterable of items to wrap
        """
        self._items: List[T] = list(items) if not isinstance(items, list) else items

    def filter(self, predicate: Callable[[T], bool]) -> 'QueryableCollection[T]':
        """
        Filter items using a predicate function.

        Args:
            predicate: Function that takes an item and returns True to include it

        Returns:
            New QueryableCollection with filtered items

        Examples:
            # Filter airports with long runways
            airports.filter(lambda a: a.longest_runway_length_ft and a.longest_runway_length_ft > 5000)

            # Filter procedures with specific characteristics
            procedures.filter(lambda p: p.is_approach() and p.approach_type == 'ILS')
        """
        return self.__class__([item for item in self._items if predicate(item)])

    def where(self, **kwargs) -> 'QueryableCollection[T]':
        """
        Filter items using keyword arguments (attribute matching).
        All conditions must match (AND logic).

        Args:
            **kwargs: Attribute name-value pairs to match

        Returns:
            New QueryableCollection with matching items

        Examples:
            # Find airport by ICAO
            airports.where(ident='EGLL')

            # Find procedures by type and runway
            procedures.where(procedure_type='approach', runway_ident='09L')
        """
        def matches(item: T) -> bool:
            return all(
                getattr(item, key, None) == value
                for key, value in kwargs.items()
            )
        return self.filter(matches)

    def first(self) -> Optional[T]:
        """
        Return the first item or None if collection is empty.

        Returns:
            First item or None

        Examples:
            # Get first airport in collection
            airport = airports.where(ident='EGLL').first()
        """
        return self._items[0] if self._items else None

    def first_or_raise(self, exception: Optional[Exception] = None) -> T:
        """
        Return the first item or raise an exception if collection is empty.

        Args:
            exception: Optional custom exception to raise. If None, raises ValueError.

        Returns:
            First item

        Raises:
            Exception if collection is empty
        """
        if not self._items:
            if exception:
                raise exception
            raise ValueError("Collection is empty")
        return self._items[0]

    def last(self) -> Optional[T]:
        """
        Return the last item or None if collection is empty.

        Returns:
            Last item or None
        """
        return self._items[-1] if self._items else None

    def all(self) -> List[T]:
        """
        Return all items as a list.

        Returns:
            List of all items

        Examples:
            # Get all filtered airports as a list
            french_airports = airports.where(iso_country='FR').all()
        """
        return self._items

    def count(self) -> int:
        """
        Return the count of items in the collection.

        Returns:
            Number of items

        Examples:
            # Count airports with procedures
            count = airports.filter(lambda a: len(a.procedures) > 0).count()
        """
        return len(self._items)

    def exists(self) -> bool:
        """
        Return True if the collection has any items.

        Returns:
            True if collection is not empty

        Examples:
            # Check if any ILS approaches exist
            has_ils = procedures.where(approach_type='ILS').exists()
        """
        return len(self._items) > 0

    def is_empty(self) -> bool:
        """
        Return True if the collection is empty.

        Returns:
            True if collection is empty
        """
        return len(self._items) == 0

    def any(self, predicate: Callable[[T], bool]) -> bool:
        """
        Return True if any item matches the predicate.

        Args:
            predicate: Function to test items

        Returns:
            True if any item matches

        Examples:
            # Check if any airport has ILS
            has_ils = airports.any(lambda a: any(p.approach_type == 'ILS' for p in a.procedures))
        """
        return any(predicate(item) for item in self._items)

    def all_match(self, predicate: Callable[[T], bool]) -> bool:
        """
        Return True if all items match the predicate.

        Args:
            predicate: Function to test items

        Returns:
            True if all items match
        """
        return all(predicate(item) for item in self._items)

    def group_by(self, key_func: Callable[[T], str]) -> Dict[str, List[T]]:
        """
        Group items by a key function.

        Args:
            key_func: Function that returns a grouping key for each item

        Returns:
            Dictionary mapping keys to lists of items

        Examples:
            # Group airports by country
            by_country = airports.group_by(lambda a: a.iso_country or 'unknown')

            # Group procedures by type
            by_type = procedures.group_by(lambda p: p.procedure_type)
        """
        result: Dict[str, List[T]] = {}
        for item in self._items:
            key = key_func(item)
            if key not in result:
                result[key] = []
            result[key].append(item)
        return result

    def order_by(self, key_func: Callable[[T], Any], reverse: bool = False) -> 'QueryableCollection[T]':
        """
        Sort items by a key function.

        Args:
            key_func: Function that returns a sort key for each item
            reverse: If True, sort in descending order

        Returns:
            New QueryableCollection with sorted items

        Examples:
            # Sort airports by name
            airports.order_by(lambda a: a.name or '')

            # Sort by longest runway (descending)
            airports.order_by(lambda a: a.longest_runway_length_ft or 0, reverse=True)
        """
        return self.__class__(sorted(self._items, key=key_func, reverse=reverse))

    def take(self, n: int) -> 'QueryableCollection[T]':
        """
        Take the first n items.

        Args:
            n: Number of items to take

        Returns:
            New QueryableCollection with first n items

        Examples:
            # Get top 10 airports by runway length
            top_10 = airports.order_by(lambda a: a.longest_runway_length_ft or 0, reverse=True).take(10)
        """
        return self.__class__(self._items[:n])

    def skip(self, n: int) -> 'QueryableCollection[T]':
        """
        Skip the first n items.

        Args:
            n: Number of items to skip

        Returns:
            New QueryableCollection with remaining items

        Examples:
            # Pagination: skip first 10, take next 10
            page_2 = airports.skip(10).take(10)
        """
        return self.__class__(self._items[n:])

    def distinct_by(self, key_func: Callable[[T], Any]) -> 'QueryableCollection[T]':
        """
        Return distinct items based on a key function.

        Args:
            key_func: Function that returns a uniqueness key for each item

        Returns:
            New QueryableCollection with distinct items (first occurrence kept)

        Examples:
            # Get distinct countries
            countries = airports.distinct_by(lambda a: a.iso_country)
        """
        seen = set()
        result = []
        for item in self._items:
            key = key_func(item)
            if key not in seen:
                seen.add(key)
                result.append(item)
        return self.__class__(result)

    def map(self, transform: Callable[[T], Any]) -> 'QueryableCollection[Any]':
        """
        Transform each item using a function.

        Args:
            transform: Function to transform each item

        Returns:
            New QueryableCollection with transformed items

        Examples:
            # Extract ICAO codes
            icao_codes = airports.map(lambda a: a.ident)

            # Extract runway counts
            runway_counts = airports.map(lambda a: len(a.runways))
        """
        return QueryableCollection([transform(item) for item in self._items])

    def to_dict(self, key_func: Callable[[T], str]) -> Dict[str, T]:
        """
        Convert to dictionary using key function.
        Raises ValueError if keys are not unique.

        Args:
            key_func: Function that returns a dict key for each item

        Returns:
            Dictionary mapping keys to items

        Examples:
            # Create ICAO -> Airport mapping
            airports_dict = airports.to_dict(lambda a: a.ident)
        """
        result = {}
        for item in self._items:
            key = key_func(item)
            if key in result:
                raise ValueError(f"Duplicate key: {key}")
            result[key] = item
        return result

    # Make the collection behave like a list
    def __iter__(self):
        """Allow iteration over items."""
        return iter(self._items)

    def __len__(self):
        """Return count of items."""
        return len(self._items)

    def __getitem__(self, index):
        """Allow indexing and slicing."""
        if isinstance(index, slice):
            return self.__class__(self._items[index])
        return self._items[index]

    def __repr__(self):
        """
        Return string representation with preview of items.

        Shows class name, preview of first few items (if they have ident/name),
        and total count.
        """
        class_name = self.__class__.__name__
        count = len(self._items)

        if count == 0:
            return f"{class_name}([])"

        # Try to build a preview of first few items
        preview_items = []
        for item in self._items[:3]:  # Show first 3 items
            # Try to get a meaningful identifier
            if hasattr(item, 'ident'):
                preview_items.append(repr(item.ident))
            elif hasattr(item, 'name'):
                preview_items.append(repr(item.name))
            else:
                # Fallback to type name for items without ident/name
                preview_items.append(f"<{type(item).__name__}>")

        # Add ellipsis if there are more items
        if count > 3:
            preview_items.append('...')

        preview = '[' + ', '.join(preview_items) + ']'
        return f"{class_name}({preview}, count={count})"

    def __bool__(self):
        """Return True if collection is not empty."""
        return len(self._items) > 0

    def __reversed__(self):
        """
        Support reversed() built-in for reverse iteration.

        Examples:
            # Iterate in reverse order
            for airport in reversed(model.airports.order_by('name')):
                print(airport.name)  # Z to A
        """
        return reversed(self._items)

    # Set operations for combining collections

    def __or__(self, other: 'QueryableCollection[T]') -> 'QueryableCollection[T]':
        """
        Union operator (|) - combine two collections, removing duplicates.

        Args:
            other: Another collection to combine with

        Returns:
            New collection with items from both collections (no duplicates)

        Examples:
            # Get airports from multiple countries
            western_europe = (
                airports.by_country("FR") |
                airports.by_country("DE") |
                airports.by_country("BE")
            )
        """
        # Use a set to remove duplicates, preserving order from first collection
        seen = set()
        result = []
        for item in self._items:
            item_id = id(item)
            if item_id not in seen:
                seen.add(item_id)
                result.append(item)
        for item in other._items:
            item_id = id(item)
            if item_id not in seen:
                seen.add(item_id)
                result.append(item)
        return self.__class__(result)

    def __and__(self, other: 'QueryableCollection[T]') -> 'QueryableCollection[T]':
        """
        Intersection operator (&) - items present in both collections.

        Args:
            other: Another collection to intersect with

        Returns:
            New collection with items present in both collections

        Examples:
            # Airports with both hard runways AND fuel
            premium = (
                airports.with_hard_runway() &
                airports.with_fuel(avgas=True, jet_a=True)
            )
        """
        other_ids = {id(item) for item in other._items}
        result = [item for item in self._items if id(item) in other_ids]
        return self.__class__(result)

    def __sub__(self, other: 'QueryableCollection[T]') -> 'QueryableCollection[T]':
        """
        Difference operator (-) - items in first collection but not in second.

        Args:
            other: Collection of items to exclude

        Returns:
            New collection with items from self that are not in other

        Examples:
            # Airports with runways but no procedures
            basic = airports.with_runways() - airports.with_procedures()

            # French airports excluding Paris area
            paris_area = airports.by_country("FR").filter(
                lambda a: a.name and 'Paris' in a.name
            )
            provincial = airports.by_country("FR") - paris_area
        """
        other_ids = {id(item) for item in other._items}
        result = [item for item in self._items if id(item) not in other_ids]
        return self.__class__(result)
