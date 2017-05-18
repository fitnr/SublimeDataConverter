# -*- coding: utf-8 -*-
import os
import csv
import _csv
import json
import re
from itertools import chain, zip_longest
import unicodedata
from pprint import pformat
import sublime
import sublime_plugin
try:
    import io
except ImportError as e:
    import StringIO as io


"""
DataConverter package for Sublime Text
https://github.com/fitnr/SublimeDataConverter

Freely adapted from Mr. Data Converter: http://shancarter.com/data_converter/
"""

# Borrowed from Apply Syntax


def sublime_format_path(pth):
    m = re.match(r"^([A-Za-z]{1}):(?:/|\\)(.*)", pth)
    if sublime.platform() == "windows" and m is not None:
        pth = m.group(1) + "/" + m.group(2)
    return pth.replace("\\", "/")


def get_type(datum):
    """ Select a data type from a (string) input"""
    try:
        int(datum)
        return int
    except ValueError:
        try:
            float(datum)
            return float
        except ValueError:
            return str

    except TypeError:
        return type(None)


def parse_types(reader):
    """ Return a list containing a best guess for the types of data in each column. """
    output_types, types = [], []

    for _ in range(10):
        try:
            row = next(reader)

        except StopIteration:
            break

        except Exception as e:
            print('DataConverter: Error parsing', e)
            break

        types.append([get_type(r) for r in row])

    # rotate the array
    types = list(zip(*types))

    for type_list in types:
        if str in type_list:
            output_types.append(str)
        elif float in type_list:
            output_types.append(float)
        else:
            output_types.append(int)

    return output_types


def set_dialect(dialectname, user_dialects):
    '''Get a CSV dialect from csv.dialects or a register one from passed dict.'''
    try:
        csv.get_dialect(dialectname)
        return dialectname

    except _csv.Error:
        try:
            user_quoting = user_dialects[dialectname].pop('quoting', 'QUOTE_MINIMAL')

            quoting = getattr(csv, user_quoting, csv.QUOTE_MINIMAL)

            csv.register_dialect(dialectname, quoting=quoting, **user_dialects[dialectname])

            print("DataConverter: Using custom dialect", dialectname)
            return dialectname

        except _csv.Error:
            print("DataConverter: Couldn't register custom dialect named", dialectname)
            return None


def sniff(sample):
    try:
        dialect = csv.Sniffer().sniff(sample)
        csv.register_dialect('sniffed', dialect)
        print('DataConverter: using sniffed dialect with delimiter:', dialect.delimiter)
        return 'sniffed'

    except _csv.Error:
        return 'excel'


def _mysql_type(t):
    if t == str:
        return 'VARCHAR(255)'
    elif t == float:
        return 'FLOAT'
    elif t == int:
        return 'INT'
    else:
        return 'TEXT'


def _sqlite_type(t):
    if t == float:
        return 'REAL'
    elif t == int:
        return 'INTEGER'
    else:
        return 'TEXT'


def _postgres_type(t):
    if t == float:
        return 'numeric'
    elif t == int:
        return 'integer'
    else:
        return 'text'

def _escape(string):
    '''Escape &, < and >'''
    return string.replace('<', '&lt;').replace('>', '&gt;')

def _length(x):
    try:
        return len(str(x))
    except TypeError:
        return 0


def _cast(value, typ_):
    try:
        return typ_(value)
    except TypeError:
        return value


def _countcombining(string):
    '''Count combining diacretics in a string.'''
    return sum(unicodedata.combining(c) > 0 for c in string)


def _countwide(string):
    '''Count the numer of wide characters in a string.'''
    return sum(unicodedata.east_asian_width(char) == 'W' for char in string)

# Adding a format? Check if it belongs in no_space_formats or untyped_formats.


class DataConverterCommand(sublime_plugin.TextCommand):

    # This will be set later on, in the converter function
    syntax = None
    settings = dict()
    escapechar = '\\'
    quotechar = "'"
    headers = []
    converter = None

    # These format can't have spaces in field names. By default, spaces replaced with "_".
    no_space_formats = (
        'actionscript',
        'javascript',
        'mysql',
        'sqlite',
        'xml',
        'xml_properties',
        'yaml'
    )

    # These formats don't need to be checked for int/str/etc types.
    untyped_formats = (
        'dsv',
        "gherkin",
        "html",
        "jira",
        "json",
        "json_columns",
        "json_rows",
        "json_keyed",
        "text_table",
        "wiki",
        "xml",
        "xml_properties",
        "yaml"
    )

    def run(self, edit, **kwargs):
        try:
            # The format key in .sublime-commands must match the name of the function we want to call.
            self.converter = getattr(self, kwargs['format'])

        except KeyError:
            print("DataConverter: no format given")
            return

        try:
            self.settings = self.get_settings(kwargs)

        except TypeError as e:
            print("DataConverter: TypeError fetching settings", e)
            return

        # If nothing is selected, select all.
        if self.view.sel()[0].empty():
            self.view.sel().add(sublime.Region(0, self.view.size()))
            deselect_flag = True

        for sel in self.view.sel():
            selection = self.view.substr(sel)
            sample = selection[:2048]

            # CSV dialect
            # Sniff if we haven't done this before, or we sniffed before.
            if 'dialect' not in self.settings or self.settings['dialect'] == 'sniffed':
                self.settings['dialect'] = sniff(sample)
                print('DataConverter: using dialect', self.settings['dialect'])

            self.headers = self.assign_headers(sample)
            data = self.import_csv(selection)

            if self.settings['typed']:
                # Assign a list of tuples (headername, type)
                self.settings['types'] = self.get_types(selection)
                print('DataConverter found these fields and types:', self.settings['types'])

            # Run converter
            converted = self.converter(data)
            self.view.replace(edit, sel, converted)
            deselect_flag = False

        if self.syntax is not None:
            self.view.set_syntax_file(self.syntax)

        if deselect_flag or self.settings.get('deselect_after'):
            self.deselect()

    def get_settings(self, kwargs):
        '''Get settings from kwargs, user settings.'''
        settings = dict()
        user_settings = sublime.load_settings('DataConverter.sublime-settings')

        # Headers
        # True, "sniff" or "never"
        settings['headers'] = user_settings.get('headers')

        # Whitespace
        # Combine headers for certain formats
        settings['mergeheaders'] = kwargs['format'] in self.no_space_formats

        # Typing
        # Don't like having 'not' in this expression, but it makes more sense to use
        # 'typed' from here on out, and it's less error prone to use the (smaller)
        # list of untyped formats.
        settings['typed'] = kwargs['format'] not in self.untyped_formats

        # New lines
        settings['newline'] = user_settings.get('line_sep') or os.linesep

        user_quoting = user_settings.get('quoting', 'QUOTE_MINIMAL')
        settings['quoting'] = getattr(csv, user_quoting, csv.QUOTE_MINIMAL)

        # Quote stripping
        settings['strip_quotes'] = user_settings.get('strip_quotes', True)

        # Indentation
        if self.view.settings().get('translate_tabs_to_spaces'):
            tabsize = int(self.view.settings().get('tab_size', 4))
            settings['indent'] = " " * tabsize
        else:
            settings['indent'] = "\t"

        # header-joiner
        settings['header_joiner'] = user_settings.get('header_joiner', '')

        # HTML characters
        settings['html_utf8'] = user_settings.get('html_utf8', True)

        # Dialect
        if user_settings.get('use_dialect', False):
            settings['dialect'] = set_dialect(user_settings.get('use_dialect'), user_settings.get('dialects', {}))

        settings['default_variable'] = user_settings.get('default_variable', 'DataConverter')

        # These settings are solely for DSV converter.
        settings['output_delimiter'] = kwargs.get('output_delimiter')
        settings['output_dialect'] = kwargs.get('output_dialect')

        return settings

    def assign_headers(self, sample):
        '''Assign headers to the data set'''
        # Use the dialect to get the first line of the sample as a dict
        # Do this here beacause we'll want the length of the data no matter what
        sample_io = io.StringIO(sample)
        headers = next(csv.reader(sample_io, dialect=self.settings['dialect']))

        if self.settings['headers'] is True:
            self.settings['has_header'] = True

        elif self.settings['headers'] is 'never':
            self.settings['has_header'] = False

        else:
            # If not told to definitely try to use headers or definitely not, we sniff for them.
            # Sniffing isn't perfect, especially with short data sets and strange delimiters
            try:
                sniffed_headers = csv.Sniffer().has_header(sample)

                if sniffed_headers:
                    self.settings['has_header'] = True
                    print("DataConverter: CSV Sniffer found headers")
                else:
                    self.settings['has_header'] = False
                    print("DataConverter: CSV Sniffer didn't find headers")

            except _csv.Error:
                print("DataConverter: CSV module had trouble sniffing for headers. Assuming they exist.")
                print('DataConverter: Add "headers": false to your settings file to assume no headers.')
                self.settings['has_header'] = True

        # Using ['val1', 'val2', ...] if 'headers=never' or Sniffer says there aren't headers
        if self.settings.get('has_header') is False:
            headers = ["val{}".format(x) for x in range(1, 1+len(headers))]

        return self.format_headers(headers)

    def format_headers(self, headers):
        '''Replace spaces in the header names for some formats.'''
        if self.settings.get('mergeheaders', False) is True:
            hj = self.settings.get('header_joiner', '_')
            headers = [x.replace(' ', hj) for x in headers]

        return headers

    def import_csv(self, selection):
        '''Read CSV data from file into a StringIO object.'''
        # Remove header from entries that came with one.
        if self.settings.get('has_header', False) is True:
            selection = selection[selection.find(self.settings['newline']):]

        csvIO = io.StringIO(selection)

        reader = csv.reader(
            csvIO,
            dialect=self.settings['dialect'])

        if self.settings.get('has_header', False) is True:
            next(reader)

        return reader

    def get_types(self, selection):
        # If untyped, return empty list.
        if self.settings.get('typed', False) is False:
            return []

        if self.settings.get('has_header', False) is True:
            selection = selection[selection.find(self.settings['newline']):]

        typer = csv.reader(
            io.StringIO(selection),
            dialect=self.settings['dialect']
        )
        if self.settings.get('has_header', False) is True:
            next(typer)

        return list(parse_types(typer))

    def deselect(self):
        """Remove selection and place pointer at top of document (adapted from https://gist.github.com/1608283)."""
        top = self.view.sel()[0].a
        self.view.sel().clear()
        self.view.sel().add(sublime.Region(top, top))

    def set_syntax(self, path, file_name=False):
        '''Set the view's syntax'''
        if not file_name:
            file_name = path

        new_syntax = sublime_format_path('/'.join(('Packages', path, file_name + '.sublime-syntax')))
        current_syntax = self.view.settings().get('syntax')

        if new_syntax != current_syntax:
            try:
                sublime.load_resource(new_syntax)
                self.view.set_syntax_file(new_syntax)
            except OSError:
                new_syntax = new_syntax.replace('.sublime-syntax', '.tmLanguage')
                try:
                    sublime.load_resource(new_syntax)
                    self.view.set_syntax_file(new_syntax)
                except OSError as err:
                    print("DataConverter: Unable to set syntax ({}).".format(err))

    def _escape(self, string):
        '''Add an escape character in front of a quote character in given string.'''
        return (string or '').replace(self.quotechar, self.escapechar + self.quotechar)

    def type_loop(self, row, field_format, field_break=None, null=None):
        """
        Helper loop for checking types as we write out a row.
        Strings get quoted, floats and ints don't.

        Args:
            row (list): returned from csv.reader
            field_format (str): format for a single field
            field_break (str): break between fields (default: ', ').
            null (str): Text to use for None values (default: 'null').

        Returns:
            str formatted with `formt` (e.g. "{0}=>{1}")
        """
        field_break = field_break or ', '
        null = null or 'null'
        types = self.settings.get('types', [])

        # Creates escaped or proper NULL representation of a value.
        def applytype(val, typ):
            if val is None:
                return null
            elif typ == str:
                return "{q}{}{q}".format(self._escape(val), q=self.quotechar)
            else:
                return _cast(val, typ)

        return field_break.join(field_format.format(field=hed, value=applytype(val, typ), q=self.quotechar)
                                for val, hed, typ in zip_longest(row, self.headers, types))

    # Converters
    # Note that converters should call self.set_syntax

    def actionscript(self, data):
        """Actionscript converter"""
        self.set_syntax('ActionScript')
        n = self.settings['newline'] + self.settings['indent']
        linebreak = '},' + n + '{'
        output = linebreak.join(self.type_loop(row, '{field}: {value}', field_break=', ') for row in data)
        return '[' + n + '{' + output + '}' + self.settings['newline'] + '];'

    # ASP / VBScript
    def asp(self, data):
        self.set_syntax('ASP')
        # comment, comment_end = "'", ""
        output = []
        C, r = 0, 0
        cell = self.settings['default_variable'] + '({c},{r})'

        for r, row in enumerate(data):
            for c, (value, typ) in enumerate(zip_longest(row, self.settings['types'])):
                typ = typ or get_type(value)
                arr = '{q}{}{q}' if typ == str else '{}'
                v = self._escape(value or 'null')
                output.append((cell + ' = ' + arr).format(v, c=c, r=r, q=self.quotechar))

            C = max(C, len(row))

        dim = 'Dim ' + cell.format(c=C, r=r, n='')
        output.insert(0, dim)
        output.insert(0, "' columnNames = Array(\"{}\")".format('", "'.join(self.headers)))
        return self.settings['newline'].join(output) + self.settings['newline']

    def _spaced_text(self, data, delimiter, row_decoration=None, **kwargs):
        '''
        General converter for formats with semantic text spacing

        Args:
            data (csv.reader): Sequence of lists
            delimiter (str): division between each field
            row_decoration (function): A function that takes Sequence of row
                                       lengths and returns a str used to optionally
                                       decorate the top, bottom, and/or between header and rows.
            field_format (str): format str for each field. default: ' {: <{fill}} '
            top (bool): Add the row decoration to the top of the output.
            between (bool): Add row decoration between the header and the row.
            bottom (bool): Add row decoration after the output.
        '''
        field_format = kwargs.get('field_format', ' {: <{fill}} ')

        # Convert data set from generator to list.
        data = list(data)

        # Get the length of each field
        lengths = [len(x) for x in self.headers]
        for row in data:
            cells = (len(unicodedata.normalize('NFKC', val)) + _countwide(val) for val in row)
            lengths = [max(i, j) for i, j in zip_longest(lengths, cells, fillvalue=0)]

        def format_row(row):
            '''Helper function that generates a sequence of formatted cells'''
            for value, width in zip_longest(row, lengths, fillvalue=''):
                # Account for fullwidth ideographs and uncombined combining diacretics.
                yield field_format.format(value, fill=width + _countcombining(value) - _countwide(value))

        # Define optional string between lines
        row_sep = row_decoration(lengths) if row_decoration else ''

        # generate a list, "head", that contains the header. It will be concat'ed with the data at the end.
        head = []
        if self.settings.get('has_header', False):
            if kwargs.get('top'):
                head.append(row_sep)

            head.append(delimiter + delimiter.join(format_row(self.headers)) + delimiter)

            if kwargs.get('between'):
                head.append(row_sep)

        # Add an optional footer below the construction
        bottom = [row_sep] if kwargs.get('bottom') else []

        # Join header and formatted body together
        return self.settings['newline'].join(chain(
            head,
            (delimiter + delimiter.join(format_row(row)) + delimiter for row in data),
            bottom
        )) + self.settings['newline']

    def dsv(self, data):
        '''
        Delimited tabular format converter.
        This is like taking coals to Newcastle, but useful for changing formats
        '''
        self.set_syntax('Plain Text')

        sink = io.StringIO()
        writer = csv.writer(sink,
                            dialect=self.settings.get('output_dialect'),
                            delimiter=self.settings.get('output_delimiter'),
                            lineterminator=self.settings.get('newline', os.linesep))
        if self.settings.get('has_header') is not False:
            writer.writerow(self.headers)
        writer.writerows(data)
        sink.seek(0)
        return sink.read()

    def html(self, data):
        """HTML Table converter."""
        # Uses {i} and {n} as shorthand for self.settings['indent'] and self.settings['newline'].
        self.set_syntax('HTML')
        thead, tbody = "", ""

        tr = "{{i}}{{i}}<tr>{{n}}{0}{{i}}{{i}}</tr>"

        # Render the table head, if there is one
        if self.settings.get('has_header') is True:
            th = '{i}{i}{i}<th>' + (
                '</th>{n}{i}{i}{i}<th>'.join(self.headers)
            ) + '</th>{n}'
            thead = '{i}<thead>{n}' + tr.format(th) + '{n}{i}</thead>{n}'

        else:
            thead = ''

        # Render table rows
        tbody = '{n}'.join(
            tr.format('{n}'.join('{i}{i}{i}<td>' + self._escape(r) + '</td>' for r in row) + '{n}')
            for row in data
        )

        table = (
            "<table>{n}" + thead + "{i}<tbody>{n}" + tbody + "{n}{i}</tbody>{n}</table>"
        ).format(i=self.settings['indent'], n=self.settings['newline'])

        if self.settings['html_utf8']:
            return table
        else:
            return table.encode('ascii', 'xmlcharrefreplace').decode('ascii')

    def gherkin(self, data):
        '''Cucumber/Gherkin converter'''
        self.set_syntax('Cucumber', 'Cucumber Steps')
        return self._spaced_text(data, '|')

    def javascript(self, data):
        """JavaScript object converter"""
        self.set_syntax('JavaScript')
        linebreak = '},' + self.settings['newline'] + self.settings['indent'] + '{'
        content = '{' + linebreak.join(self.type_loop(r, '"{field}": {value}', ', ') for r in data) + '}'

        return '[' + self.settings['newline'] + self.settings['indent'] + content + self.settings['newline'] + '];'

    def jira(self, data):
        head = '||' + ('||').join(self.headers) + '||' + self.settings['newline']

        fmt = '|' + ('|{}' * len(self.headers)) + '|'
        print('DataConverter: Formatting JIRA row with', fmt)
        content = (self.settings['newline']).join(fmt.format(*r) for r in data)

        return head + content + self.settings['newline']

    def json(self, data):
        """JSON properties converter"""
        self.set_syntax('JavaScript', 'JSON')
        return json.dumps([dict(zip(self.headers, row)) for row in data],
                          indent=len(self.settings['indent']), ensure_ascii=False)

    def json_columns(self, data):
        """JSON Array of Columns converter"""
        self.set_syntax('JavaScript', 'JSON')
        return json.dumps(list(zip_longest(*data)), indent=len(self.settings['indent']), separators=(',', ':'))

    def json_rows(self, data):
        """JSON Array of Rows converter"""
        self.set_syntax('JavaScript', 'JSON')
        return json.dumps(list(data), indent=len(self.settings['indent']), separators=(',', ':'))

    def json_keyed(self, data):
        """JSON, first row is key"""
        self.set_syntax('JavaScript', 'JSON')
        try:
            keydict = {self._escape(row[0]): {k: v for k, v in zip_longest(self.headers, row)} for row in data}
        except IndexError:
            raise IndexError('Problem converting to dictionary. Check that there are no empty rows.')

        return json.dumps(keydict, indent=len(self.settings['indent']), separators=(',', ':'))

    def markdown(self, data):
        """markdown table format"""
        self.set_syntax('Text', 'Markdown')

        def decorate(lengths):
            fields = '|'.join(' ' + ('-' * v) + ' ' for v in lengths)
            return '|' + fields + '|'

        return self._spaced_text(data, '|', decorate, between=True)

    def mysql(self, data):
        """MySQL converter"""
        fields = ',{n}{i}'.join(h + ' ' + _mysql_type(t) for h, t in zip(self.headers, self.settings['types']))
        create = (
            'CREATE TABLE IF NOT EXISTS {table} ('
            '{n}{i}id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,{n}' +
            '{i}' + fields + '{n}'
            ');'
        )
        return self._sql(data, create)

    def perl(self, data):
        """Perl converter"""
        self.set_syntax('Perl')
        output = "}},{n}{i}{{".join(self.type_loop(r, '{q}{field}{q}=>{value}', null='undef') for r in data)
        return ("[{n}{i}{{" + output + '}}{n}];').format(n=self.settings['newline'], i=self.settings['indent'])

    def _php(self, data, array_open, array_close):
        """General PHP Converter"""
        self.set_syntax('PHP')

        return array_open + self.settings['newline'] + ("," + self.settings['newline']).join(
            self.settings['indent'] + array_open + self.type_loop(row, '{q}{field}{q}=>{value}') + array_close
            for row in data
        ) + self.settings['newline'] + array_close + ";"

    def php4(self, data):
        """Older-style PHP converter"""
        return self._php(data, 'array(', ')')

    def php54(self, data):
        """PHP 5.4 converter"""
        return self._php(data, '[', ']')

    def postgres(self, data):
        '''PostgreSQL converter'''
        fields = ',{n}{i}'.join(h + ' ' + _postgres_type(t) for h, t in zip(self.headers, self.settings['types']))
        create = (
            'CREATE TABLE IF NOT EXISTS {table} ({n}'
            '{i}id serial,{n}' +
            '{i}' + fields + '{n}'
            ');'
        )
        return self._sql(data, create)

    def python_dict(self, data):
        """Python dict converter"""
        self.set_syntax('Python')

        fields = [{k: _cast(v, t) for k, v, t in zip_longest(self.headers, row, self.settings['types'])}
                  for row in data]
        return pformat(fields)

    def python_list(self, data):
        """Python list of lists converter"""
        self.set_syntax('Python')
        fields = [[_cast(r, t) for r, t in zip_longest(row, self.settings['types'])] for row in data]
        return '# headers = {}{n}{}'.format(self.headers, pformat(fields), n=self.settings['newline'])

    def ruby(self, data):
        """Ruby converter"""
        self.set_syntax('Ruby')
        # comment, comment_end = "#", ""
        output = '}},{n}{i}{{'.join(self.type_loop(row, '{q}{field}{q}=>{value}', null='nil') for row in data)
        return ('[{n}{i}{{' + output + '}}{n}];').format(n=self.settings['newline'], i=self.settings['indent'])

    def _sql(self, data, create):
        '''General SQL converter, used by MySQL, PostgreSQL, SQLite.'''
        # Uses {i} and {n} as shorthand for self.settings['indent'] and self.settings['newline'].
        self.set_syntax('SQL')
        fmt = (
            create + '{n}' +
            'INSERT INTO {table}{n}{i}({names}){n}VALUES{n}'
            '{i}(' +
            '),{n}{i}('.join(self.type_loop(row, field_format='{value}', null='NULL') for row in data) +
            ');'
        )
        return fmt.format(create=create, table=self.settings['default_variable'], names=', '.join(self.headers),
                          i=self.settings['indent'], n=self.settings['newline'])

    def sqlite(self, data):
        '''SQLite converter'''
        fields = ',{n}{i}'.join(h + ' ' + _sqlite_type(t) for h, t in zip(self.headers, self.settings['types']))
        create = (
            'CREATE TABLE IF NOT EXISTS {table} ({n}'
            '{i}id INTEGER PRIMARY KEY ON CONFLICT FAIL AUTOINCREMENT,{n}'
            '{i}' + fields +
            '{n});'
        )

        return self._sql(data, create)

    def wiki(self, data):
        '''Wiki table converter'''
        n = self.settings['newline']
        linebreak = '{0}|-{0}|'.format(n)
        header = '{| class="wikitable"' + n + '!' + ('!!').join(self.headers)

        return header + linebreak + linebreak.join(self.type_loop(row, '{value}', '||') for row in data) + n + '|}'

    def xml(self, data):
        """XML Nodes converter"""
        self.set_syntax('XML')
        elem = '{{i}}{{i}}<{1}>{0}</{1}>'
        rows = '{n}'.join(
            '{i}<row>{n}' + '{n}'.join(
                elem.format(_escape(value or ""), head) for head, value in zip(self.headers, row)
            ) + "{n}{i}</row>"
            for row in data
        )
        output = '<?xml version="1.0" encoding="UTF-8"?>{n}<rows>{n}' + rows + "{n}</rows>"
        return output.format(i=self.settings['indent'], n=self.settings['newline'])

    def xml_properties(self, data):
        """XML properties converter"""
        self.set_syntax('XML')
        rows = '{n}'.join(
            "{i}<row " +
            ' '.join('{0}="{1}"'.format(head, value or "") for head, value in zip(self.headers, row)) +
            "></row>"
            for row in data
        )
        output = '<?xml version="1.0" encoding="UTF-8"?>{n}<rows>{n}' + rows + "{n}</rows>"
        return output.format(i=self.settings['indent'], n=self.settings['newline'])

    def xml_illustrator(self, data):
        '''Convert to Illustrator XML format'''
        self.set_syntax('XML')

        output = (
            '<?xml version="1.0" encoding="utf-8"?>{n}'
            '<!DOCTYPE svg PUBLIC "-//W3C//DTD SVG 20001102//EN"    '
            '"http://www.w3.org/TR/2000/CR-SVG-20001102/DTD/svg-20001102.dtd" [{n}'
            '{i}<!ENTITY ns_graphs "http://ns.adobe.com/Graphs/1.0/">{n}'
            '{i}<!ENTITY ns_vars "http://ns.adobe.com/Variables/1.0/">{n}'
            '{i}<!ENTITY ns_imrep "http://ns.adobe.com/ImageReplacement/1.0/">{n}'
            '{i}<!ENTITY ns_custom "http://ns.adobe.com/GenericCustomNamespace/1.0/">{n}'
            '{i}<!ENTITY ns_flows "http://ns.adobe.com/Flows/1.0/">{n}'
            '{i}<!ENTITY ns_extend "http://ns.adobe.com/Extensibility/1.0/">{n}'
            ']>{n}'
            '<svg>{n}'
            '<variableSets  xmlns="&ns_vars;">{n}'
            '{i}<variableSet  varSetName="binding1" locked="none">{n}'
            '{i}{i}<variables>{n}'
        )

        for header in self.headers:
            output += ('{i}' * 3) + '<variable varName="' + header + \
                '" trait="textcontent" category="&ns_flows;"></variable>' + '{n}'

        output += (
            '{i}{i}</variables>{n}'
            '{i}{i}'
            '<v:sampleDataSets  '
            'xmlns:v="http://ns.adobe.com/Variables/1.0/" '
            'xmlns="http://ns.adobe.com/GenericCustomNamespace/1.0/">{n}'
        )

        field = ('{{i}}' * 4) + '<{field}>{{n}}' + ('{{i}}' * 5) + '<p>{value}</p>{{n}}' + ('{{i}}' * 4) + '</{field}>'

        for row in data:
            output += (
                ('{i}' * 3) + '<v:sampleDataSet dataSetName="' + row[0] + '">{n}' +
                '{n}'.join(field.format(field=f, value=_escape(v)) for f, v in zip(self.headers, row)) + '{n}' +
                ('{i}' * 3) + '</v:sampleDataSet>{n}'
            )

        output += (
            '{i}{i}</v:sampleDataSets>{n}'
            '{i}</variableSet>{n}'
            '</variableSets>{n}'
            '</svg>{n}'
        )

        return output.format(i=self.settings['indent'], n=self.settings['newline'])

    def text_table(self, data):
        """text table converter"""
        self.set_syntax('Text', 'Plain Text')

        def decorate(lengths):
            return '+' + '+'.join('-' * (v + 2) for v in lengths) + '+'

        return self._spaced_text(data, '|', decorate, top=True, between=True, bottom=True)

    def yaml(self, data):
        '''YAML Converter'''
        self.set_syntax('YAML')
        linebreak = '{n}-{n}{i}'
        rows = (self.type_loop(r, '{field}: {value}', '{n}{i}') for r in data)
        return ('---' + linebreak + linebreak.join(rows) + '{n}').format(n=self.settings['newline'], i=self.settings['indent'])
