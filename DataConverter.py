# -*- coding: utf-8 -*-
import sublime
import sublime_plugin
import csv
import _csv
import json
import re
import pprint
from collections import OrderedDict
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


def parse_types(reader, headers):
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

        tmp = []

        for h in headers:
            typ = get_type(row[h])
            tmp.append(typ)

        types.append(tmp)

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


def _length(x):
    try:
        return len(str(x))
    except TypeError:
        return 0


# Adding a format? Check if it belongs in no_space_formats or untyped_formats.


class DataConverterCommand(sublime_plugin.TextCommand):

    # This will be set later on, in the converter function
    syntax = None
    settings = dict()
    escapechar = '\\'
    quotechar = '"'

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

            headers = self.assign_headers(sample)
            data = self.import_csv(selection, headers)

            # Assign a list of tuples (headername, type)
            self.settings['types'] = self.get_types(selection, headers)
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
        settings['newline'] = user_settings.get('line_sep') or '\n'

        user_quoting = user_settings.get('quoting', 'QUOTE_MINIMAL')
        settings['quoting'] = getattr(csv, user_quoting, csv.QUOTE_MINIMAL)

        # Indentation
        if self.view.settings().get('translate_tabs_to_spaces'):
            tabsize = int(self.view.settings().get('tab_size', 4))
            settings['indent'] = " " * tabsize
        else:
            settings['indent'] = "\t"

        # HTML characters
        settings['html_utf8'] = user_settings.get('html_utf8', True)

        # Dialect
        if user_settings.get('use_dialect', False):
            settings['dialect'] = set_dialect(user_settings.get('use_dialect'), user_settings.get('dialects', {}))

        settings['default_variable'] = user_settings.get('default_variable', 'DataConverter')

        # These settings are solely for DSV converter.
        settings['output_delimiter'] = kwargs.get('output_delimiter')

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

        if self.settings.get('strip_quotes', True):
            headers = [j.strip('"\'') for j in headers]

        return headers

    def import_csv(self, selection, headers):
        '''Read CSV data from file into a StringIO object.'''
        # Remove header from entries that came with one.
        if self.settings.get('has_header', False) is True:
            selection = selection[selection.find(self.settings['newline']):]

        csvIO = io.StringIO(selection)

        reader = csv.DictReader(
            csvIO,
            fieldnames=headers,
            dialect=self.settings['dialect'])

        return reader

    def get_types(self, selection, headers):
        # If untypes, we don't want any quoting, so treat everything like an int
        if self.settings.get('typed', False) is False:
            return list(zip(headers, (int,) * len(headers)))

        if self.settings.get('has_header', False) is True:
            selection = selection[selection.find(self.settings['newline']):]

        typer = csv.DictReader(
            io.StringIO(selection),
            fieldnames=headers,
            dialect=self.settings['dialect']
        )
        types = parse_types(typer, headers)

        return list(zip(headers, types))

    def deselect(self):
        """Remove selection and place pointer at top of document (adapted from https://gist.github.com/1608283)."""
        top = self.view.sel()[0].a
        self.view.sel().clear()
        self.view.sel().add(sublime.Region(top, top))

    def set_syntax(self, path, file_name=False):
        if not file_name:
            file_name = path

        file_name = file_name + '.tmLanguage'
        new_syntax = sublime_format_path('/'.join(['Packages', path, file_name]))

        current_syntax = self.view.settings().get('syntax')

        if new_syntax != current_syntax:
            try:
                sublime.load_resource(new_syntax)
                self.view.set_syntax_file(new_syntax)
            except Exception:
                print("Unable to set syntax.")

    def _escape(self, string):
        '''Add an escape character in front of a quote character in given string.'''
        return string.replace(self.quotechar, self.escapechar + self.quotechar)

    def type_loop(self, row, field_format, field_break=None, null=None):
        """
        Helper loop for checking types as we write out a row.
        Strings get quoted, floats and ints don't.

        Args:
            row (dict): returned from DictReader
            field_format (str): format for a single field
            field_break (str): break between fields (default: ', ').
            null (str): Text to use for None values (default: 'null').

        Returns:
            str formatted with `formt` (e.g. "{0}=>{1}")
        """
        field_break = field_break or ', '
        null = null or 'null'

        # Creates escaped or proper NULL representation of a value.
        def applytypes(key, typ):
            if key not in row or row[key] is None:
                return null
            elif typ == str:
                return '"{}"'.format(self._escape(row[key]))
            else:
                return row[key]

        return field_break.join(field_format.format(field, applytypes(field, typ)) for field, typ in self.settings['types'])

    # Converters
    # Note that converters should call self.set_syntax

    def actionscript(self, data):
        """Actionscript converter"""
        self.set_syntax('ActionScript')
        n = self.settings['newline'] + self.settings['indent']
        linebreak = '},' + n + '{'
        output = linebreak.join(self.type_loop(row, '{0}: {1}', field_break=', ') for row in data)
        return '[' + n + '{' + output + '}' + self.settings['newline'] + '];'

    # ASP / VBScript
    def asp(self, data):
        self.set_syntax('ASP')
        #comment, comment_end = "'", ""
        output = ''
        c, r = 0, 0
        cell = self.settings['newline'] + self.settings['default_variable'] + '({0},{1}) = '

        for r, row in enumerate(data):
            for c, (key, item_type) in enumerate(self.settings['types']):
                if item_type == str:
                    row[key] = '"{}"'.format(self._escape(row.get(key) or ''))
                elif item_type is None:
                    row[key] = 'null'

                output += cell.format(c, r) + row[key]

        return 'Dim ' + cell.format(c, r)[1:-3] + output

    def _spaced_text(self, data, delimiter, row_decoration=None, **kwargs):
        '''
        General converter for formats with semantic text spacing

        Args:
            data (DictReader): Sequence of dicts
            delimiter (str): division between each field
            row_decoration (function): A function that takes Sequence of row
                                       lengths and returns a str used to optionally
                                       decorate the top, bottom, and/ot between header and rows.
            field_format (str): format str for each field. default: ' {: <{fill}} '
            top (bool): Add the row decoration to the top of the output.
            between (bool): Add row decoration between the header and the row.
            bottom (bool): Add row decoration after the output.
        '''
        field_format = kwargs.get('field_format', ' {: <{fill}} ')
        fieldnames = data.fieldnames
        # Get the length of each field
        field_lengths = [len(x) for x in fieldnames]

        data = list(data)

        for row in data:
            for k, v in row.items():
                field_lengths[fieldnames.index(k)] = max(field_lengths[fieldnames.index(k)], len(v))

        row_sep = ''
        if row_decoration:
            row_sep = row_decoration(field_lengths)

        if self.settings.get('has_header', False):
            header = (field_format.format(f, fill=field_lengths[j]) for j, f in enumerate(fieldnames))
            head = delimiter + delimiter.join(header) + delimiter + self.settings['newline']

            if kwargs.get('top'):
                head = row_sep + head

            if kwargs.get('between'):
                head += row_sep
        else:
            head = ''

        output_text = delimiter + (delimiter + self.settings['newline'] + delimiter).join(
            delimiter.join(
                field_format.format(row[f], fill=field_lengths[j]) for j, f in enumerate(fieldnames)
            ) for row in data
        ) + delimiter + self.settings['newline']

        if kwargs.get('bottom'):
            output_text += row_sep

        return head + output_text

    def dsv(self, data):
        '''
        Delimited tabular format converter
        This is like taking coals to Newcastle, but useful for changing formats
        '''
        self.set_syntax('Plain Text')

        sink = io.StringIO()
        writer = csv.DictWriter(sink, data.fieldnames,
                                delimiter=self.settings['output_delimiter'],
                                lineterminator=self.settings['newline'])
        if self.settings.get('has_header') is not False:
            writer.writeheader()
        writer.writerows(data)
        sink.seek(0)
        return sink.read()

    def html(self, data):
        """HTML Table converter."""
        # Uses {i} and {n} as shorthand for self.settings['indent'] and self.settings['newline'].
        self.set_syntax('HTML')
        thead, tbody = "", ""

        def tr(row):
            return "{i}{i}<tr>{n}" + row + "{i}{i}</tr>{n}"

        # Render the table head, if there is one
        if self.settings.get('has_header') is True:

            th = '{i}{i}{i}<th>' + (
                    '</th>{n}{i}{i}{i}<th>'.join(header for header in data.fieldnames)
                ) + '</th>{n}'

            thead = '{i}<thead>{n}' + tr(th) + '{i}</thead>{n}'
        else:
            thead = ''

        # Render table rows
        for row in data:
            rowText = ""

            for key in data.fieldnames:
                rowText += '{i}{i}{i}<td>' + self._escape(row[key] or "") + '</td>{n}'

            tbody += tr(rowText)

        table = "<table>{n}" + thead + "{i}<tbody>{n}" + tbody + "{i}</tbody>{n}</table>"

        if self.settings['html_utf8']:
            return table.format(i=self.settings['indent'], n=self.settings['newline'])
        else:
            return table.format(i=self.settings['indent'], n=self.settings['newline']).encode('ascii', 'xmlcharrefreplace')

    def gherkin(self, data):
        '''Cucumber/Gherkin converter'''
        self.set_syntax('Cucumber', 'Cucumber Steps')
        return self._spaced_text(data, '|')

    def javascript(self, data):
        """JavaScript object converter"""
        self.set_syntax('JavaScript')

        linebreak = '},' + self.settings['newline'] + self.settings['indent'] + '{'

        content = '{' + linebreak.join(self.type_loop(r, '"{0}": {1}', ', ') for r in data) + '}'

        return '[' + self.settings['newline'] + self.settings['indent'] + content + self.settings['newline'] + '];'

    def jira(self, data):
        head = '||' + ('||').join(data.fieldnames) + '||' + self.settings['newline']

        fmt = '|' + ('|'.join('{' + x + '}' for x in data.fieldnames)) + '|'
        print('DataConverter: Formatting JIRA row with', fmt)
        content = (self.settings['newline']).join(fmt.format(**r) for r in data)

        return head + content + self.settings['newline']

    def json(self, data):
        """JSON properties converter"""
        self.set_syntax('JavaScript', 'JSON')
        return json.dumps([row for row in data], ensure_ascii=False)

    def json_columns(self, data):
        """JSON Array of Columns converter"""
        self.set_syntax('JavaScript', 'JSON')
        colDict = {}

        for row in data:
            for key, item in row.items():
                if key not in colDict:
                    colDict[key] = []
                colDict[key].append(item)
        return json.dumps(colDict, indent=len(self.settings['indent']), separators=(',', ':'))

    def json_rows(self, data):
        """JSON Array of Rows converter"""
        self.set_syntax('JavaScript', 'JSON')
        rowArrays = []

        for row in data:
            itemlist = []
            for item in row.values():
                itemlist.append(item)
            rowArrays.append(itemlist)

        return json.dumps(rowArrays, indent=len(self.settings['indent']), separators=(',', ':'))

    def json_keyed(self, data):
        """JSON, first row is key"""
        self.set_syntax('JavaScript', 'JSON')

        key = data.fieldnames[0]
        keydict = {self._escape(row[key]): {k: v for k, v in row.items() if k != key} for row in data}

        return json.dumps(keydict, indent=len(self.settings['indent']), separators=(',', ':'))

    def markdown(self, data):
        """markdown table format"""
        self.set_syntax('Text', 'Markdown')

        def decorate(lengths):
            fields = '|'.join(' ' + ('-' * v) + ' ' for v in lengths)
            return '|' + fields + '|' + self.settings['newline']

        return self._spaced_text(data, '|', decorate, between=True)

    def mysql(self, data):
        """MySQL converter"""
        # Uses {i} and {n} as shorthand for self.settings['indent'] and self.settings['newline'].
        self.set_syntax('SQL')
        table = self.settings['default_variable']

        # CREATE TABLE statement
        create_head = 'CREATE TABLE IF NOT EXISTS' + table + ' ({n}{i}id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,{n}'
        create_fields = ',{n}{i}'.join(h + ' ' + _mysql_type(t) for h, t in self.settings['types'])

        create = create_head + '{i}' + create_fields + '{n}) CHARACTER SET utf8;{n}'

        # INSERT TABLE Statement
        insert = 'INSERT INTO ' + table + "{n}{i}(" + ', '.join(data.fieldnames) + '){n}'

        # VALUES list
        values = "VALUES{n}{i}(" + ('),{n}{i}('.join(self.type_loop(row, field_format='{1}', null='NULL') for row in data))

        output = create + insert + values + ');'
        return output.format(i=self.settings['indent'], n=self.settings['newline'])

    def perl(self, data):
        """Perl converter"""
        self.set_syntax('Perl')

        linebreak = "}," + self.settings['newline'] + "{"
        output = linebreak.join(self.type_loop(r, '"{0}"=>{1}', null='undef') for r in data)

        return "[" + self.settings['newline'] + '{' + output + '}' + self.settings['newline'] + '];'

    def _php(self, data, array_open, array_close):
        """General PHP Converter"""
        self.set_syntax('PHP')

        return array_open + self.settings['newline'] + ("," + self.settings['newline']).join(
            self.settings['indent'] + array_open + self.type_loop(row, '"{0}"=>{1}') + array_close
            for row in data
        ) + self.settings['newline'] + array_close + ";"

    def php4(self, data):
        """Older-style PHP converter"""
        return self._php(data, 'array(', ')')

    def php54(self, data):
        """PHP 5.4 converter"""
        return self._php(data, '[', ']')

    def python_dict(self, data):
        """Python dict converter"""
        self.set_syntax('Python')
        fields = []
        for row in data:
            outrow = {}
            for k, t in self.settings['types']:
                if t == int:
                    outrow[k] = int(row[k])
                elif t == float:
                    outrow[k] = float(row[k])
                else:
                    outrow[k] = row[k]
            fields.append(outrow)

        return pprint.pformat(fields)

    def python_list(self, data):
        """Python list of lists converter"""
        self.set_syntax('Python')
        fields = []
        for row in data:
            outrow = []
            for k, t in self.settings['types']:
                if t == int:
                    outrow.append(int(row[k]))
                elif t == float:
                    outrow.append(float(row[k]))
                else:
                    outrow.append(row[k])
            fields.append(outrow)

        return '# headers = ' + repr(data.fieldnames) + self.settings['newline'] + pprint.pformat(fields)

    def ruby(self, data):
        """Ruby converter"""
        self.set_syntax('Ruby')
        # comment, comment_end = "#", ""

        linebreak = '},' + self.settings['newline'] + self.settings['indent'] + '{'
        output = linebreak.join(self.type_loop(row, '"{0}"=>{1}', null='nil') for row in data)

        return '[' + self.settings['newline'] + self.settings['indent'] + '{' + output + '}' + self.settings['newline'] + '];'

    def sqlite(self, data):
        '''SQLite converter'''
        self.set_syntax('SQL')
        table = self.settings['default_variable']
        create_head = 'CREATE TABLE IF NOT EXISTS ' + table + ' ({n}{i}id INTEGER PRIMARY KEY ON CONFLICT FAIL AUTOINCREMENT,{n}'
        create_fields = ',{n}{i}'.join(h + ' ' + _sqlite_type(t) for h, t in self.settings['types'])
        create = create_head + '{i}' + create_fields + '{n});{n}'

        # INSERT TABLE Statement
        insert = 'INSERT INTO ' + table + "{n}{i}(" + ', '.join(data.fieldnames) + '){n}'

        # VALUES list
        values = "VALUES{n}{i}(" + ('),{n}{i}('.join(self.type_loop(row, field_format='{1}', null='NULL') for row in data))

        output = create + insert + values + ');'
        return output.format(i=self.settings['indent'], n=self.settings['newline'])

    def wiki(self, data):
        '''Wiki table converter'''
        n = self.settings['newline']

        linebreak = '{0}|-{0}|'.format(n)

        header = '{| class="wikitable"' + n + '!' + ('!!').join(data.fieldnames)

        return header + linebreak + linebreak.join(self.type_loop(row, '{1}', '||') for row in data) + n + '|}'

    def xml(self, data):
        """XML Nodes converter"""
        self.set_syntax('XML')
        output_text = '<?xml version="1.0" encoding="UTF-8"?>{n}<rows>{n}'

        for row in data:
            output_text += '{i}<row>{n}'
            for header in data.fieldnames:
                output_text += '{i}{i}<{1}>{0}</{1}>{n}'.format(row[header] or '', header, i=self.settings['indent'], n=self.settings['newline'])

            output_text += "{i}</row>{n}"

        output_text += "</rows>"

        return output_text.format(i=self.settings['indent'], n=self.settings['newline']).encode('ascii', 'xmlcharrefreplace').decode('ascii', 'xmlcharrefreplace')

    def xml_properties(self, data):
        """XML properties converter"""
        self.set_syntax('XML')
        output_text = '<?xml version="1.0" encoding="UTF-8"?>{n}<rows>{n}'

        for row in data:
            row_list = []

            for header in data.fieldnames:
                item = row[header] or ""
                row_list.append('{0}="{1}"'.format(header, item))
                row_text = " ".join(row_list)

            output_text += "{i}<row " + row_text + "></row>{n}"

        output_text += "</rows>"

        return output_text.format(i=self.settings['indent'], n=self.settings['newline']).encode('ascii', 'xmlcharrefreplace').decode('ascii', 'xmlcharrefreplace')

    def xml_illustrator(self, data):
        '''Convert to Illustrator XML format'''
        self.set_syntax('XML')

        output = '<?xml version="1.0" encoding="utf-8"?>' + '{n}'
        output += '<!DOCTYPE svg PUBLIC "-//W3C//DTD SVG 20001102//EN"    "http://www.w3.org/TR/2000/CR-SVG-20001102/DTD/svg-20001102.dtd" [' + '{n}'
        output += '{i}' + '<!ENTITY ns_graphs "http://ns.adobe.com/Graphs/1.0/">' + '{n}'
        output += '{i}' + '<!ENTITY ns_vars "http://ns.adobe.com/Variables/1.0/">' + '{n}'
        output += '{i}' + '<!ENTITY ns_imrep "http://ns.adobe.com/ImageReplacement/1.0/">' + '{n}'
        output += '{i}' + '<!ENTITY ns_custom "http://ns.adobe.com/GenericCustomNamespace/1.0/">' + '{n}'
        output += '{i}' + '<!ENTITY ns_flows "http://ns.adobe.com/Flows/1.0/">' + '{n}'
        output += '{i}' + '<!ENTITY ns_extend "http://ns.adobe.com/Extensibility/1.0/">' + '{n}'
        output += ']>' + '{n}'
        output += '<svg>' + '{n}'
        output += '<variableSets  xmlns="&ns_vars;">' + '{n}'
        output += '{i}' + '<variableSet  varSetName="binding1" locked="none">' + '{n}'
        output += '{i}{i}' + '<variables>' + '{n}'

        for header in data.fieldnames:
            output += ('{i}' * 3) + '<variable varName="' + header + '" trait="textcontent" category="&ns_flows;"></variable>' + '{n}'

        output += '{i}{i}' + '</variables>' + '{n}'
        output += '{i}{i}' + '<v:sampleDataSets  xmlns:v="http://ns.adobe.com/Variables/1.0/" xmlns="http://ns.adobe.com/GenericCustomNamespace/1.0/">' + '{n}'

        for row in data:
            output += ('{i}' * 3) + '<v:sampleDataSet dataSetName="' + row[data.fieldnames[0]] + '">' + '{n}'

            for field in data.fieldnames:
                output += ('{i}' * 4) + '<' + field + '>' + '{n}'
                output += ('{i}' * 5) + '<p>' + row[field] + '</p>' + '{n}'
                output += ('{i}' * 4) + '</' + field + '>' + '{n}'

            output += ('{i}' * 3) + '</v:sampleDataSet>' + '{n}'

        output += '{i}{i}' + '</v:sampleDataSets>' + '{n}'
        output += '{i}' + '</variableSet>' + '{n}'
        output += '</variableSets>' + '{n}'
        output += '</svg>' + '{n}'

        return output.format(i=self.settings['indent'], n=self.settings['newline'])

    def text_table(self, data):
        """text table converter"""
        self.set_syntax('Text', 'Plain Text')

        def decorate(lengths):
            return '+' + '+'.join('-' * (v + 2) for v in lengths) + '+' + self.settings['newline']

        return self._spaced_text(data, '|', decorate, top=True, between=True, bottom=True)

    def yaml(self, data):
        '''YAML Converter'''
        self.set_syntax('YAML')
        linebreak = '{n}-{n}{i}'
        rows = (self.type_loop(r, '{0}: {1}', '{n}{i}') for r in data)
        return ('---' + linebreak + linebreak.join(rows) + '{n}').format(n=self.settings['newline'], i=self.settings['indent'])
