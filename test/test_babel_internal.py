import unittest

from babelsdk.data_type import (
    Boolean,
    Float32,
    Int32,
    Int64,
    List,
    String,
    Timestamp,
    UInt32,
    UInt64,
)

from babelsdk.data_type import (
    Field,
    Struct,
    SymbolField,
    Union,
)

class TestBabelInternal(unittest.TestCase):
    """
    Tests the internal representation of a Babel.
    """

    def test_list(self):

        l = List(String(), min_items=1, max_items=3)

        # check proper list
        l.check(['1'])

        # check bad item type
        with self.assertRaises(ValueError) as cm:
            l.check([1.5])
        self.assertIn('not a valid string', cm.exception.args[0])

        # check too many items
        with self.assertRaises(ValueError) as cm:
            l.check(['e1', 'e2', 'e3', 'e4'])
        self.assertIn('more than 3 items', cm.exception.args[0])

        # check too few items
        with self.assertRaises(ValueError) as cm:
            l.check([])
        self.assertIn('fewer than 1 items', cm.exception.args[0])

    def test_string(self):

        s = String(min_length=1, max_length=3)

        # check correct str
        s.check('1')

        # check correct unicode
        s.check(u'\u2650')

        # check bad item
        with self.assertRaises(ValueError) as cm:
            s.check(99)
        self.assertIn('not a valid string', cm.exception.args[0])

        # check too many characters
        with self.assertRaises(ValueError) as cm:
            s.check('12345')
        self.assertIn('more than 3 characters', cm.exception.args[0])

        # check too few characters
        with self.assertRaises(ValueError) as cm:
            s.check('')
        self.assertIn('fewer than 1 characters', cm.exception.args[0])

    def test_int(self):

        i = Int32()

        # check valid Int32
        i.check(42)

        # check number that is too large
        with self.assertRaises(ValueError) as cm:
            i.check(2**31)
        self.assertIn('not within range', cm.exception.args[0])

        # check number that is too small
        with self.assertRaises(ValueError) as cm:
            i.check(-2**31-1)
        self.assertIn('not within range', cm.exception.args[0])

        i = UInt32()

        # check number that is too large
        with self.assertRaises(ValueError) as cm:
            i.check(2**32)
        self.assertIn('not within range', cm.exception.args[0])

        # check number that is too small
        with self.assertRaises(ValueError) as cm:
            i.check(-1)
        self.assertIn('not within range', cm.exception.args[0])

        i = Int64()

        # check number that is too large
        with self.assertRaises(ValueError) as cm:
            i.check(2**63)
        self.assertIn('not within range', cm.exception.args[0])

        # check number that is too small
        with self.assertRaises(ValueError) as cm:
            i.check(-2**63-1)
        self.assertIn('not within range', cm.exception.args[0])

        i = UInt64()

        # check number that is too large
        with self.assertRaises(ValueError) as cm:
            i.check(2**64)
        self.assertIn('not within range', cm.exception.args[0])

        # check number that is too small
        with self.assertRaises(ValueError) as cm:
            i.check(-1)
        self.assertIn('not within range', cm.exception.args[0])

    def test_boolean(self):

        b = Boolean()

        # check valid bool
        b.check(True)

        # check non-bool
        with self.assertRaises(ValueError) as cm:
            b.check('true')
        self.assertIn('not a valid boolean', cm.exception.args[0])

    def test_float(self):

        f = Float32()

        # check valid float
        f.check(3.14)

        # check non-float
        with self.assertRaises(ValueError) as cm:
            f.check('1.1')
        self.assertIn('not a valid float', cm.exception.args[0])

        # TODO: Need to check float range once it's been implemented.

    def test_timestamp(self):
        t = Timestamp('%a, %d %b %Y %H:%M:%S')

        # check valid timestamp
        t.check('Sat, 21 Aug 2010 22:31:20')

        # check bad timestamp
        with self.assertRaises(ValueError) as cm:
            t.check('Sat, 21 Aug 2010')
        self.assertIn('does not match format', cm.exception.args[0])

    def test_struct(self):

        quota_info = Struct(
            'QuotaInfo',
            "Information about a user's space quota.",
            [
             Field('quota', UInt64(), 'Total amount of space.'),
             ],
        )

        # add a example that doesn't fit the definition of a struct
        with self.assertRaises(KeyError) as cm:
            quota_info.add_example('default', {'bad_field': 'xyz123'})
        self.assertIn('has invalid fields', cm.exception.args[0])

        quota_info.add_example('default', {'quota': 64000})

        # set null for a non-nullable field
        with self.assertRaises(ValueError) as cm:
            quota_info.add_example('null', {'quota': None})
        self.assertIn('field is not nullable', cm.exception.args[0])

        self.assertTrue(quota_info.has_example('default'))

        # test for structs within structs
        quota_info = Struct(
            'AccountInfo',
            "Information about an account.",
            [
             Field('account_id', String(), 'Unique identifier for account.'),
             Field('quota_info', quota_info, 'Quota', nullable=True)
            ],
        )

        quota_info.add_example('default', {'account_id': 'xyz123'})

        # ensure that an example for quota_info is propagated up
        self.assertIn('quota_info', quota_info.get_example('default'))

    def test_union(self):

        update_parent_rev = Struct(
            'UpdateParentRev',
            "Overwrite existing file if the parent rev matches.",
            [
                Field('parent_rev', String(), 'The revision to be updated.')
            ]
        )
        update_parent_rev.add_example('default', {'parent_rev': 'xyz123'})

        # test variants with only tags, as well as those with structs.
        conflict = Union(
            'WriteConflictPolicy',
            'Policy for managing write conflicts.',
            [
                SymbolField('reject', 'On a write conflict, reject the new file.'),
                SymbolField('overwrite', 'On a write conflict, overwrite the existing file.'),
                Field('update_if_matching_parent_rev',
                      update_parent_rev,
                      'On a write conflict, overwrite the existing file.'),
            ]
        )

        # test that only a symbol is returned for an example of a SymbolField
        self.assertEqual(conflict.get_example('reject'), 'reject')

        # test that dict is returned for a tagged struct variant
        self.assertIn('update_if_matching_parent_rev', conflict.get_example('default'))
