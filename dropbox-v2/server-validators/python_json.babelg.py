"""
BabelAPI Code Generator for the Dropbox Python v2 SDK.

TODO: With a little bit more abstraction and better modularity, this could
become the general "Babel-Python" generator, and wouldn't have to be Dropbox-
specific at all.
"""

import re
from babelapi.data_type import (
    Binary,
    Boolean,
    CompositeType,
    Float32,
    Float64,
    Field,
    Int32,
    Int64,
    List,
    Null,
    String,
    Struct,
    SymbolField,
    Timestamp,
    UInt32,
    UInt64,
    Union,
)
from babelapi.data_type import (
    is_composite_type,
    is_integer_type,
    is_list_type,
    is_null_type,
    is_string_type,
    is_struct_type,
    is_timestamp_type,
    is_union_type,
)
from babelapi.generator.generator import CodeGeneratorMonolingual
from babelapi.lang.python import PythonTargetLanguage

base = """\
import copy
import datetime
import numbers
import six

import babel_data_types as dt

"""

# Matches format of Babel doc tags
doc_sub_tag_re = re.compile(':(?P<tag>[A-z]*):`(?P<val>.*?)`')

class PythonSDKGenerator(CodeGeneratorMonolingual):
    """Generates Python modules for the Dropbox Python v2 SDK that implement
    the data types defined in the spec."""

    lang = PythonTargetLanguage()

    def generate(self):
        """
        Generates a module for each namespace.

        Each namespace will have Python classes to represent structs and unions
        in the Babel spec. The namespace will also have a class of the same
        name but prefixed with "Base" that will have methods that represent
        the routes specified in the Babel spec.
        """
        for namespace in self.api.namespaces.values():
            with self.output_to_relative_path('{}.py'.format(namespace.name)):
                self._generate_base_namespace_module(namespace)

    def _generate_base_namespace_module(self, namespace):
        """Creates a module for the namespace. All data types are represented
        as classes."""
        self.emit(base)
        for data_type in namespace.linearize_data_types():
            if is_struct_type(data_type):
                self._generate_struct_class(data_type)
            elif is_union_type(data_type):
                self._generate_union_class(data_type)
            else:
                raise TypeError('Cannot handle type %r' % type(data_type))

    def emit_wrapped_indented_lines(self, s):
        """Emits wrapped lines. All lines are the first are indented."""
        self.emit_wrapped_lines(s,
                                prefix='    ',
                                first_line_prefix=False)

    def docf(self, doc):
        """
        Substitutes tags in Babel docs with their Python-doc-friendly
        counterparts. A tag has the following format:

        :<tag>:`<value>`

        Example tags are 'route' and 'struct'.
        """
        if not doc:
            return
        for match in doc_sub_tag_re.finditer(doc):
            matched_text = match.group(0)
            tag = match.group('tag')
            val = match.group('val')
            if tag == 'struct':
                doc = doc.replace(matched_text, ':class:`{}`'.format(val))
            elif tag == 'route':
                doc = doc.replace(matched_text, val)
            elif tag == 'link':
                anchor, link = val.rsplit(' ', 1)
                doc = doc.replace(matched_text, '`{} <{}>`_'.format(anchor, link))
            elif tag == 'val':
                doc = doc.replace(matched_text, '{}'.format(self.lang.format_obj(val)))
            else:
                doc = doc.replace(matched_text, '``{}``'.format(val))
        return doc

    #
    # Struct Types
    #

    def _generate_struct_class(self, data_type):
        """Defines a Python class that represents a struct in Babel."""
        self.emit_line(self._class_declaration_for_data_type(data_type))
        with self.indent():
            if data_type.doc:
                self.emit_line('"""')
                self.emit_wrapped_lines(self.docf(data_type.doc))
                self.emit_empty_line()
                for field in data_type.fields:
                    if field.doc:
                        self.emit_wrapped_indented_lines(':ivar {}: {}'.format(
                            self.lang.format_variable(field.name),
                            self.docf(field.doc),
                        ))
                self.emit_line('"""')
            self.emit_empty_line()

            self._generate_struct_class_vars(data_type)
            self._generate_struct_class_init(data_type)
            self._generate_struct_class_validate(data_type)
            self._generate_struct_class_properties(data_type)
            self._generate_struct_class_from_dict(data_type)
            self._generate_struct_class_to_dict(data_type)
            self._generate_struct_class_repr(data_type)

    def _format_type_in_doc(self, data_type):
        if is_null_type(data_type):
            return 'None'
        elif is_composite_type(data_type):
            return ':class:`{}`'.format(self.lang.format_type(data_type))
        else:
            return self.lang.format_type(data_type)

    def _func_args_from_dict(self, d):
        filtered_d = self._filter_out_none_valued_keys(d)
        return ', '.join(['%s=%s' % (k, v) for k, v in filtered_d.items()])

    def _generate_struct_class_vars(self, data_type):
        """
        Each class has a class attribute for each field that is a primitive type.
        The attribute is a validator for the field.
        """
        lineno = self.lineno
        for field in data_type.fields:
            if not is_composite_type(field.data_type):
                if is_list_type(field.data_type):
                    # TODO: Support embedded lists
                    self.emit_line('__{}_data_type = dt.List({})'.format(
                        self.lang.format_variable(field.name),
                        self._func_args_from_dict({
                            'data_type': field.data_type.data_type.name,
                            'min_length': field.data_type.min_items,
                            'max_length': field.data_type.max_items,
                        })
                    ))
                elif is_integer_type(field.data_type):
                    self.emit_line('__{}_data_type = dt.{}({})'.format(
                        self.lang.format_variable(field.name),
                        field.data_type.name,
                        self._func_args_from_dict({
                            'min_value': field.data_type.min_value,
                            'max_value': field.data_type.max_value,
                        })
                    ))
                elif is_string_type(field.data_type):
                    self.emit_line('__{}_data_type = dt.String({})'.format(
                        self.lang.format_variable(field.name),
                        self._func_args_from_dict({
                            'min_length': field.data_type.min_length,
                            'max_length': field.data_type.max_length,
                            'pattern': repr(field.data_type.pattern),
                        })
                    ))
                elif is_timestamp_type(field.data_type):
                    self.emit_line('__{}_data_type = dt.Timestamp({})'.format(
                        self.lang.format_variable(field.name),
                        self._func_args_from_dict({
                            'format': repr(field.data_type.format),
                        })
                    ))
                else:
                    self.emit_line('__{}_data_type = dt.{}()'.format(
                        self.lang.format_variable(field.name),
                        field.data_type.name,
                    ))
        if lineno != self.lineno:
            self.emit_empty_line()

        self.emit_line('__fields = {')
        with self.indent():
            for field in data_type.all_fields:
                self.emit_line("'{}',".format(self.lang.format_variable(field.name)))
        self.emit_line('}')
        self.emit_empty_line()

    def _generate_struct_class_init(self, data_type):
        """Generates constructor for struct."""
        self.emit_line('def __init__(self):')
        with self.indent():
            lineno = self.lineno

            # Call the parent constructor if a super type exists
            if data_type.super_type:
                class_name = self._class_name_for_data_type(data_type)
                self.emit_line('super({}, self).__init__()'.format(class_name))

            for field in data_type.fields:
                field_var_name = self.lang.format_variable(field.name)
                self.emit_line('self._{} = None'.format(field_var_name))
                self.emit_line('self.__has_{} = False'.format(field_var_name))

            if lineno == self.lineno:
                self.emit_line('pass')
            self.emit_empty_line()

    def _generate_struct_class_validate(self, data_type):
        self.emit_line('def validate(self):')
        with self.indent():
            self.emit_line('return all([')
            with self.indent():
                for field in data_type.all_required_fields:
                    field_name = self.lang.format_method(field.name)
                    self.emit_line('self.__has_{},'.format(field_name))
            self.emit_line('])')
            self.emit_empty_line()

    def _generate_struct_class_properties(self, data_type):
        for field in data_type.fields:
            field_name = self.lang.format_method(field.name)

            # generate getter for field
            self.emit_line('@property')
            self.emit_line('def {}(self):'.format(field_name))
            with self.indent():
                if field.doc:
                    self.emit_line('"""')
                    self.emit_wrapped_lines(self.docf(field.doc))
                    self.emit_line('"""')
                self.emit_line('if self.__has_{}:'.format(field_name))
                with self.indent():
                    self.emit_line('return self._{}'.format(field_name))

                self.emit_line('else:')
                with self.indent():
                    if field.optional:
                        if field.has_default:
                            self.emit_line(self.lang.format_obj(field.default))
                        else:
                            self.emit_line('return None')
                    else:
                        self.emit_line('raise KeyError("missing required field {!r}")'.format(field_name))
            self.emit_empty_line()

            # generate setter for field
            self.emit_line('@{}.setter'.format(field_name))
            self.emit_line('def {}(self, val):'.format(field_name))
            with self.indent():
                if is_composite_type(field.data_type):
                    class_name = self.lang.format_class(field.data_type.name)
                    self.emit_line('if not isinstance(val, {}):'.format(class_name))
                    with self.indent():
                        self.emit_line("raise TypeError('{} is of type %r but must be of type {}' % type(val).__name__)".format(field_name, class_name))
                    self.emit_line('val.validate()'.format(field_name))
                else:
                    self.emit_line('self.__{}_data_type.validate(val)'.format(field_name))
                self.emit_line('self._{} = val'.format(field_name))
                self.emit_line('self.__has_{} = True'.format(field_name))
            self.emit_empty_line()

            # generate deleter for field
            self.emit_line('@{}.deleter'.format(field_name))
            self.emit_line('def {}(self, val):'.format(field_name))
            with self.indent():
                self.emit_line('self._{} = None'.format(field_name))
                self.emit_line('self.__has_{} = False'.format(field_name))
            self.emit_empty_line()

    def _generate_struct_class_repr(self, data_type):
        """The special __repr__() function will return a string of the class
        name, and if the class has fields, the first field as well."""
        self.emit_line('def __repr__(self):')
        with self.indent():
            if data_type.fields:
                self.emit_line("return '{}(%r)' % self._{}".format(
                    self._class_name_for_data_type(data_type),
                    data_type.fields[0].name,
                ))
            else:
                self.emit_line("return '{}()'".format(self._class_name_for_data_type(data_type)))
        self.emit_empty_line()

    def _generate_struct_class_from_dict(self, data_type):
        """The from_json() function will convert a Python dictionary object
        that presumably was constructed from JSON into a Python object
        of the correct type."""
        self.emit_line('@classmethod')
        self.emit_line('def from_dict(cls, transformer, obj):')
        with self.indent():
            self.emit_line('for key in obj:')
            with self.indent():
                self.emit_line('if key not in cls.__fields:')
                with self.indent():
                    self.emit_line('raise KeyError("Unknown key: %r" % key)')
            var_name = self.lang.format_variable(data_type.name)
            self.emit_line('{} = {}()'.format(var_name, self.lang.format_class(data_type.name)))
            for field in data_type.all_fields:
                field_name = self.lang.format_variable(field.name)
                if field.optional:
                    if is_composite_type(field.data_type):
                        self.emit_line("if obj.get('{}') is not None:".format(field_name))
                        with self.indent():
                            self.emit_line("{0}.{1} = {2}.from_dict(transformer, obj['{1}'])".format(
                                var_name,
                                field_name,
                                self.lang.format_class(field.data_type.name),
                            ))
                    else:
                        self.emit_line("{0}.{1} = transformer.convert_from({0}.__{1}_data_type, obj.get('{1}'))".format( var_name, field_name))
                else:
                    self.emit_line("if '{}' not in obj:".format(field_name))
                    with self.indent():
                        self.emit_line('raise KeyError("missing required field {!r}")'.format(field_name))
                    if is_composite_type(field.data_type):
                        self.emit_line("{0}.{1} = {2}.from_dict(transformer, obj['{1}'])".format(
                            var_name,
                            field_name,
                            self.lang.format_class(field.data_type.name),
                        ))
                    else:
                        self.emit_line("{0}.{1} = transformer.convert_from({0}.__{1}_data_type, obj['{1}'])".format(var_name, field_name))

            self.emit_line('return {}'.format(var_name))
        self.emit_empty_line()

    def _generate_struct_class_to_dict(self, data_type):
        """The to_json() function will convert a Python object into a
        dictionary that can be serialized into JSON."""
        self.emit_line('def to_dict(self, transformer):')
        with self.indent():
            self.emit_line('d = dict', trailing_newline=False)
            args = []
            for field in data_type.all_required_fields:
                if is_composite_type(field.data_type):
                    args.append('{0}=self._{0}.to_dict(transformer)'.format(field.name))
                else:
                    args.append('{0}=transformer.convert_to(self.__{0}_data_type, self._{0})'.format(field.name))
            self._generate_func_arg_list(args, compact=True)
            self.emit_empty_line()
            for field in data_type.all_optional_fields:
                self.emit_line('if self._{} is not None:'.format(field.name))
                with self.indent():
                    if is_composite_type(field.data_type):
                        self.emit_line("d['{0}'] = self._{0}.to_dict(transformer)".format(field.name))
                    else:
                        self.emit_line("d['{0}'] = transformer.convert_to(self.__{0}_data_type, self._{0})".format(field.name))
            self.emit_line('return d')
        self.emit_empty_line()

    def _class_name_for_data_type(self, data_type):
        return self.lang.format_class(data_type.name)

    def _class_declaration_for_data_type(self, data_type):
        if data_type.super_type:
            extends = self._class_name_for_data_type(data_type.super_type)
        else:
            extends = 'object'
        return 'class {}({}):'.format(self._class_name_for_data_type(data_type), extends)

    def _is_instance_type(self, data_type):
        """The Python types to use in a call to isinstance() for the specified
        Babel data_type."""
        if isinstance(data_type, (UInt32, UInt64, Int32, Int64)):
            return 'numbers.Integral'
        elif isinstance(data_type, String):
            return 'six.string_types'
        elif is_timestamp_type(data_type):
            return 'datetime.datetime'
        else:
            return self.lang.format_type(data_type)

    #
    # Tagged Union Types
    #

    def _generate_union_class(self, data_type):
        """Defines a Python class that represents a union in Babel."""
        self.emit_line(self._class_declaration_for_data_type(data_type))
        with self.indent():
            if data_type.doc:
                self.emit_line('"""')
                self.emit_wrapped_lines(self.docf(data_type.doc))
                self.emit_empty_line()
                for field in data_type.fields:
                    if isinstance(field, SymbolField):
                        ivar_doc = ':ivar {}: {}'.format(self.lang.format_class(field.name),
                                                         self.docf(field.doc))
                    elif is_composite_type(field.data_type):
                        ivar_doc = ':ivar {}: {}'.format(
                            self.lang.format_class(field.name),
                            self.docf(field.doc),
                        )
                    self.emit_wrapped_indented_lines(ivar_doc)
                self.emit_line('"""')
            self.emit_empty_line()

            for field in data_type.fields:
                if isinstance(field, SymbolField):
                    self.emit_line('{} = object()'.format(self.lang.format_class(field.name)))
                elif is_composite_type(field.data_type):
                    self.emit_line('{0} = {1}'.format(self.lang.format_class(field.name),
                                                      self._class_name_for_data_type(field.data_type)))
                else:
                    raise ValueError('Only symbols and composite types for union fields.')
            self.emit_empty_line()

            self._generate_union_class_init(data_type)
            self._generate_union_class_validate(data_type)
            self._generate_union_class_is_set(data_type)
            self._generate_union_class_properties(data_type)
            self._generate_union_class_from_dict(data_type)
            self._generate_union_class_to_dict(data_type)
            self._generate_union_class_repr(data_type)

    def _generate_union_class_init(self, data_type):
        """Generates the __init__ method for the class."""
        self.emit_line('def __init__(self):')
        with self.indent():
            lineno = self.lineno

            # Call the parent constructor if a super type exists
            if data_type.super_type:
                class_name = self._class_name_for_data_type(data_type)
                self.emit_line('super({}, self).__init__()'.format(class_name))

            for field in data_type.fields:
                field_var_name = self.lang.format_variable(field.name)
                if not isinstance(field, SymbolField):
                    self.emit_line('self._{} = None'.format(field_var_name))
            if lineno == self.lineno:
                self.emit_line('pass')
            self.emit_line('self.__tag = None')
            self.emit_empty_line()

    def _generate_union_class_validate(self, data_type):
        self.emit_line('def validate(self):')
        with self.indent():
            self.emit_line('return self.__tag is not None')
        self.emit_empty_line()

    def _generate_union_class_is_set(self, data_type):
        for field in data_type.fields:
            field_name = self.lang.format_method(field.name)
            self.emit_line('def is_{}(self):'.format(field_name))
            with self.indent():
                self.emit_line('return self.__tag == {!r}'.format(field_name))
            self.emit_empty_line()

    def _generate_union_class_properties(self, data_type):
        for field in data_type.fields:
            field_name = self.lang.format_method(field.name)

            if isinstance(field, SymbolField):
                self.emit_line('def set_{}(self):'.format(field_name))
                with self.indent():
                    self.emit_line('self.__tag = {!r}'.format(field_name))
                self.emit_empty_line()
                continue

            # generate getter for field
            self.emit_line('@property')
            self.emit_line('def {}(self):'.format(field_name))
            with self.indent():
                self.emit_line('if not self.is_{}():'.format(field_name))
                with self.indent():
                    self.emit_line('raise KeyError("tag {!r} not set")'.format(field_name))
                if isinstance(field, SymbolField):
                    self.emit_line('return {!r}'.format(field_name))
                else:
                    self.emit_line('return self._{}'.format(field_name))
            self.emit_empty_line()

            # generate setter for field
            self.emit_line('@{}.setter'.format(field_name))
            self.emit_line('def {}(self, val):'.format(field_name))
            with self.indent():
                if is_composite_type(field.data_type):
                    class_name = self.lang.format_class(field.data_type.name)
                    self.emit_line('if not isinstance(val, {}):'.format(class_name))
                    with self.indent():
                        self.emit_line("raise TypeError('{} is of type %r but must be of type {}' % type(val).__name__)".format(field_name, class_name))
                    self.emit_line('val.validate()'.format(field_name))
                else:
                    self.emit_line('self.__{}_data_type.validate(val)'.format(field_name))
                self.emit_line('self._{} = val'.format(field_name))
                self.emit_line('self.__tag = {!r}'.format(field_name))
            self.emit_empty_line()

    def _generate_union_class_from_dict(self, data_type):
        """The from_json() function will convert a Python dictionary object
        that presumably was constructed from JSON into a Python object
        of the correct type."""
        self.emit_line('@classmethod')
        self.emit_line('def from_dict(cls, transformer, obj):')
        with self.indent():
            var_name = self.lang.format_variable(data_type.name)
            self.emit_line('{} = cls()'.format(var_name))
            self.emit_line('if isinstance(obj, dict) and len(obj) != 1:')
            with self.indent():
                self.emit_line('raise KeyError("Union can only have one key set not %d" % len(obj))')
            for field in data_type.all_fields:
                if isinstance(field, SymbolField):
                    self.emit_line("if obj == '{}':".format(field.name))
                    with self.indent():
                        self.emit_line('{}.set_{}()'.format(var_name, self.lang.format_method(field.name)))
                elif is_composite_type(field.data_type):
                    self.emit_line("if isinstance(obj, dict) and '{}' == obj.keys()[0]:".format(field.name))
                    with self.indent():
                        composite_assignment = "{0}.{1} = {2}.from_dict(transformer, obj['{1}'])".format(
                            var_name,
                            self.lang.format_variable(field.name),
                            self._class_name_for_data_type(field.data_type),
                        )
                        self.emit_line(composite_assignment)
                else:
                    self.emit_line("if isinstance(obj, dict) and '{}' == obj.keys()[0]:".format(field.name))
                    with self.indent():
                        composite_assignment = "{0}.{1} = transformer.convert_from(self.__{1}_data_type, obj['{1}'])".format(
                            var_name,
                            self.lang.format_variable(field.name),
                            self._class_name_for_data_type(field.data_type),
                        )
                        self.emit_line(composite_assignment)

            self.emit_line('return {}'.format(var_name))
            self.emit_empty_line()

    def _generate_union_class_to_dict(self, data_type):
        """The to_dict() function will convert a Python object into a
        dictionary that can be serialized into JSON."""
        self.emit_line('def to_dict(self, transformer):')
        with self.indent():
            for field in data_type.all_fields:
                self.emit_line("if self.is_{}():".format(field.name))
                with self.indent():
                    if isinstance(field, SymbolField):
                        self.emit_line('return {!r}'.format(self.lang.format_variable(field.name)))
                    elif is_composite_type(field.data_type):
                        self.emit_line('return dict({0}=self.{0}.to_dict(transformer))'.format(field.name))
                    else:
                        self.emit_line('return dict({0}=transformer.convert_to(self.__{0}_data_type, self._{0})'.format(field.name))
        self.emit_empty_line()

    def _generate_union_class_repr(self, data_type):
        # The special __repr__() function will return a string of the class
        # name, and the selected tag
        self.emit_line('def __repr__(self):')
        with self.indent():
            if data_type.fields:
                self.emit_line("return '{}(%r)' % self.__tag".format(
                    self._class_name_for_data_type(data_type),
                ))
            else:
                self.emit_line("return '{}()'".format(self._class_name_for_data_type(data_type)))
        self.emit_empty_line()