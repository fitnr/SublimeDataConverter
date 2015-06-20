# -*- coding: utf-8 -*-
"""
DataConverter package for Sublime Text
https://github.com/fitnr/SublimeDataConverter

Freely adapted from Mr. Data Converter: http://shancarter.com/data_converter/
"""

import sublime
import sublime_plugin
import csv
import _csv
import re
import pprint
try:
    import io
except ImportError as e:
    import StringIO as io


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


def parse(reader, headers):
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

    print('DataConverter found these output types:', output_types)
    return output_types


def tr(row):
    """Helper for HTML converter"""
    return "{i}{i}<tr>{n}" + row + "{i}{i}</tr>{n}"

def set_dialect(dialectname, user_dialects):

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

class DataConverterCommand(sublime_plugin.TextCommand):

    # This will be set later on, in the converter function
    syntax = None
    settings = dict()
    escapechar = '\\'
    quotechar = '"'

    no_space_formats = [
        'actionscript',
        'javascript',
        'mysql',
        'xml',
        'xml_properties',
        'yaml'
    ]

    untyped_formats = [
        "html",
        "jira",
        "json",
        "json_columns",
        "json_rows",
        "json_keyed",
        "text_table",
        "wiki"
        "xml",
        "xml_properties",
        "yaml"
    ]

    def run(self, edit, **kwargs):
        try:
            self.get_settings(kwargs)

        except TypeError as e:
            print("DataConverter: TypeError fetching settings", e)
            return

        except Exception as e:
            print("DataConverter: Error fetching settings. Did you specify a format?", e)
            return

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
            #  This also assigns types (for typed formats)
            data = self.import_csv(selection, headers)

            # Run converter
            converted = self.converter(data)
            self.view.replace(edit, sel, converted)
            deselect_flag = False

        if self.syntax is not None:
            self.view.set_syntax_file(self.syntax)

        if deselect_flag or self.settings.get('deselect_after'):
            self.deselect()

    def get_settings(self, kwargs):
        '''
        Adding a format? Check if it belongs in no_space_formats and untyped_formats.
        untyped_formats: don't need to be checked for int/str/etc types.
        no_space_formats: can't have spaces in their headers. By default, spaces replaced with "_".
        '''

        user_settings = sublime.load_settings('DataConverter.sublime-settings')

        # The format key in .sublime-commands must match the name of the function we want to call.
        self.converter = getattr(self, kwargs['format'])

        # Headers
        # True, "sniff" or "never"
        self.settings['headers'] = user_settings.get('headers')

        # Whitespace
        # Combine headers for certain formats
        self.settings['mergeheaders'] = kwargs['format'] in self.no_space_formats

        # Typing
        # Don't like having 'not' in this expression, but it makes more sense to use 'typed' from here on out
        # And it's less error prone to use the (smaller) list of untyped formats
        self.settings['typed'] = kwargs['format'] not in self.untyped_formats

        # New lines
        line_sep = user_settings.get('line_sep')
        self.settings['newline'] = line_sep or '\n'

        user_quoting = user_settings.get('quoting', 'QUOTE_MINIMAL')
        self.settings['quoting'] = getattr(csv, user_quoting, csv.QUOTE_MINIMAL)

        # Indentation
        if (self.view.settings().get('translate_tabs_to_spaces')):
            tabsize = int(self.view.settings().get('tab_size', 4))
            self.settings['indent'] = " " * tabsize
        else:
            self.settings['indent'] = "\t"

        # HTML characters
        self.settings['html_utf8'] = user_settings.get('html_utf8', True)

        # Dialect
        if user_settings.get('use_dialect', False):
            self.settings['dialect'] = set_dialect(user_settings.get('use_dialect'), user_settings.get('dialects', {}))

        self.settings['default_variable'] = user_settings.get('default_variable', 'DataConverter')

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
            headers = ["val" + str(x) for x in range(len(headers))]

        return self.format_headers(headers)

    def format_headers(self, headers):
        # Replace spaces in the header names for some formats.
        if self.settings.get('mergeheaders', False) is True:
            hj = self.settings.get('header_joiner', '_')
            headers = [x.replace(' ', hj) for x in headers]

        if self.settings.get('strip_quotes', True):
            headers = [j.strip('"\'') for j in headers]

        return headers

    def import_csv(self, selection, headers):
        # Remove header from entries that came with one.
        if self.settings.get('has_header', False) is True:
            selection = selection[selection.find(self.settings['newline']):]

        csvIO = io.StringIO(selection)

        reader = csv.DictReader(
            csvIO,
            fieldnames=headers,
            dialect=self.settings['dialect'])

        if self.settings.get('typed', False) is True:
            # Another reader for checking field types.
            typerIO = io.StringIO(selection)
            typer = csv.DictReader(typerIO, fieldnames=headers, dialect=self.settings['dialect'])
            self.settings['types'] = parse(typer, headers)

        return reader

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
        return string.replace(self.quotechar, self.escapechar + self.quotechar)

    def type_loop(self, row, headers, formt, nulltxt='null'):
        """
        Helper loop for checking types as we write out a row.
        Strings get quoted, floats and ints don't.
        row is a dictionary returned from DictReader
        Returns a line of code formatted with `formt` (e.g. "{0}=>{1}, ")

        """
        out = ''

        for key, typ in zip(headers, self.settings['types']):

            if key not in row or row[key] is None:
                txt = nulltxt
            elif typ == str:
                txt = '"' + self._escape(row[key]) + '"'
            else:
                txt = row[key]

            out += formt.format(key, txt)

        return out

    # Converters
    # Note that converters should call self.set_syntax

    def actionscript(self, data):
        """Actionscript converter"""

        self.set_syntax('ActionScript')

        output = "["

        # begin render loops
        for row in data:
            output += "{"
            output += self.type_loop(row, data.fieldnames, '{0}:{1},')

            output = output[0:-1] + "}" + "," + self.settings['newline']

        return output[:-2] + "];"

    # ASP / VBScript
    def asp(self, data):
        self.set_syntax('ASP')
        #comment, comment_end = "'", ""
        output, r = "", 0
        c = len(data.fieldnames)

        for row in data:

            for c, key, item_type in zip(range(len(data.fieldnames)), data.fieldnames, self.settings['types']):
                if item_type == str:
                    row[key] = '"' + self._escape(row[key] or "") + '"'
                if item_type is None:
                    row[key] = 'null'

                output += 'myArray({0},{1}) = {2}'.format(c, r, row[key] + self.settings['newline'])
            r = r + 1

        dim = 'Dim myArray({0},{1}){2}'.format(c, r - 1, self.settings['newline'])

        return dim + output

    def html(self, data):
        """HTML Table converter.
        We use {i} and {n} as shorthand for self.settings['indent'] and self.settings['newline']."""

        self.set_syntax('HTML')
        thead, tbody = "", ""

        # Render the table head, if there is one
        if self.settings.get('has_header') is True:
            for header in data.fieldnames:
                thead += '{i}{i}{i}<th>' + header + '</th>{n}'

            thead = '{i}<thead>{n}' + tr(thead) + '{i}</thead>{n}'
        else:
            thead = ''

        # Render table rows
        for row in data:
            rowText = ""

            for key in data.fieldnames:
                rowText += '{i}{i}{i}<td>' + self._escape(row[key] or "") + '</td>{n}'

            tbody += tr(rowText)

        table = "<table>{n}" + thead
        table += "{i}<tbody>{n}" + tbody + "{i}</tbody>{n}</table>"

        if self.settings['html_utf8']:
            return table.format(i=self.settings['indent'], n=self.settings['newline'])
        else:
            return table.format(i=self.settings['indent'], n=self.settings['newline']).encode('ascii', 'xmlcharrefreplace')

    def gherkin(self, data):
        '''Cucumber/Gherkin converter'''
        self.set_syntax('Cucumber', 'Cucumber Steps')
        output = "|"

        for header in data.fieldnames:
            output += header + "\t|"

        output += self.settings['newline']

        for row in data:
            output += "|" + self.type_loop(row, data.fieldnames, "{1}\t|", 'nil') + self.settings['newline']

        return output

    def javascript(self, data):
        """JavaScript object converter"""

        self.set_syntax('JavaScript')
        output = '[' + self.settings['newline']

        for row in data:
            output += self.settings['indent'] + "{" + self.type_loop(row, data.fieldnames, '{0}: {1}, ')
            output = output[:-2] + "}," + self.settings['newline']

        return output[:-2] + self.settings['newline'] + '];'

    def jira(self, data):
        sep = '|'
        output = (sep * 2) + (sep * 2).join(data.fieldnames) + (sep * 2) + self.settings['newline']

        for row in data:
            output += sep + sep.join(row.values()) + sep + self.settings['newline']

        return output

    def json(self, data):
        """JSON properties converter"""
        import json
        self.set_syntax('JavaScript', 'JSON')
        return json.dumps([row for row in data], ensure_ascii=False)

    def json_columns(self, data):
        """JSON Array of Columns converter"""
        import json
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
        import json
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
        import json
        self.set_syntax('JavaScript', 'JSON')

        key = data.fieldnames[0]
        keydict = {self._escape(row[key]): {k: v for k, v in row.items() if k != key} for row in data}

        return json.dumps(keydict, indent=len(self.settings['indent']), separators=(',', ':'))

    def mysql(self, data):
        """MySQL converter
        We use {i} and {n} as shorthand for self.settings['indent'] and self.settings['newline']."""
        self.set_syntax('SQL')

        table = self.settings['default_variable']

        # CREATE TABLE statement
        create = 'CREATE TABLE ' + table + '({n}'
        create += self.settings['indent'] + "id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,{n}"

        # INSERT TABLE Statement
        insert = 'INSERT INTO ' + table + " {n}{i}("

        # VALUES list
        values = "VALUES" + self.settings['newline']

        # Loop through headers
        for header, typ in zip(data.fieldnames, self.settings['types']):
            if typ == str:
                typ = 'VARCHAR(255)'
            elif typ == float:
                typ = 'FLOAT'
            elif typ == int:
                typ = 'INT'

            insert += header + ","

            create += '{i}' + header + " " + typ + "," + self.settings['newline']

        create = create[:-2] + '{n}'  # Remove the comma and line_sep
        create += ") CHARACTER SET utf8;{n}"

        insert = insert[:-1] + ") {n}"

        for row in data:
            values += self.settings['indent'] + "("
            values += self.type_loop(row, data.fieldnames, formt='{1},', nulltxt='NULL')

            values = values[:-1] + '),' + self.settings['newline']

        output = create + insert + values[:-2] + ';'
        return output.format(i=self.settings['indent'], n=self.settings['newline'])

    def perl(self, data):
        """Perl converter"""
        self.set_syntax('Perl')
        output = "["

        for row in data:
            output += "{"
            output += self.type_loop(row, data.fieldnames, '"{0}"=>{1}, ', nulltxt='undef')

            output = output[:-2] + "}," + self.settings['newline']

        return output[:-2] + "];"

    def php(self, data, array_open, array_close):
        """General PHP Converter"""
        self.set_syntax('PHP')
        #comment, comment_end = "//", ""

        output = array_open + self.settings['newline']

        for row in data:
            output += self.settings['indent'] + array_open
            output += self.type_loop(row, data.fieldnames, '"{0}"=>{1}, ')
            output = output[:-2] + array_close + "," + self.settings['newline']

        return output[:-1] + self.settings['newline'] + array_close + ";"

    def php4(self, data):
        """Older-style PHP converter"""
        return self.php(data, 'array(', ')')

    def php54(self, data):
        """PHP 5.4 converter"""
        return self.php(data, '[', ']')

    def python_dict(self, data):
        """Python dict converter"""
        self.set_syntax('Python')
        fields = []
        for row in data:
            outrow = {}
            for k, t in zip(data.fieldnames, self.settings['types']):
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
            for k, t in zip(data.fieldnames, self.settings['types']):
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
        output = "["

        for row in data:
            output += "{"
            output += self.type_loop(row, data.fieldnames, '"{0}"=>{1}, ', nulltxt='nil')

            output = output[:-2] + "}," + self.settings['newline']

        return output[:-2] + "];"

    def wiki(self, data):
        '''Wiki table converter'''
        # self.set_syntax('Text', 'Plain text')
        headsep, colsep = '!', '|'

        output = '{| class="wikitable"' + self.settings['newline']
        output += headsep + (headsep * 2).join(data.fieldnames) + self.settings['newline']

        for row in data:
            output += '|-' + self.settings['newline']
            output += colsep + (colsep * 2).join(row.values()) + self.settings['newline']

        return output + '|}'

    def xml(self, data):
        """XML Nodes converter"""
        self.set_syntax('XML')
        output_text = '<?xml version="1.0" encoding="UTF-8"?>{n}<rows>{n}'

        for row in data:
            output_text += '{i}<row>{n}'
            for header in data.fieldnames:
                item = row[header] or ""
                output_text += '{i}{i}<{1}>{0}</{1}>{n}'.format(item, header, i=self.settings['indent'], n=self.settings['newline'])

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
        output_text, divline, field_length, _data = '|', '+', [], []

        _data = [x for x in data]

        for header in data.fieldnames:
            length = len(header) + 1  # Add 1 to account for end-padding

            for row in _data:
                try:
                    length = max(length, len(row[header]) + 1)
                except TypeError:
                    pass

            field_length.append(length)
            divline += '-' * (length + 1) + '+'
            output_text += ' ' + header + ' ' * (length - len(header)) + '|'

        divline += '{n}'

        if self.settings.get('has_header', False):
            output_text = '{0}{1}{{n}}{0}'.format(divline, output_text)
        else:
            output_text = divline

        for row in _data:
            row_text = '|'

            for header, length in zip(data.fieldnames, field_length):
                item = row[header] or ""
                row_text += ' ' + item + ' ' * (length - len(item)) + '|'

            output_text += row_text + "{n}"

        output_text += divline
        return output_text.format(n=self.settings['newline'])

    def yaml(self, data):
        '''YAML Converter'''

        #  Set the syntax of the document.
        #  In ST2 the syntax of this line is different
        self.set_syntax('YAML')

        #  The DataConverterCommand has two useful values
        #  for formatting text: self.settings['newline'] and self.settings['indent']
        #  They respect the user's text settings
        output_text = "---" + self.settings['newline']

        #  data is a csv.reader object
        #  We use the `.fieldnames` parameter to keep header names straight
        #  For typed formats requiring, self.settings['types'] is a list of the sniffed Python types of each column
        for row in data:
            output_text += "-" + self.settings['newline']

            for header in data.fieldnames:
                output_text += "  " + header + ": " + row.get(header, '') + self.settings['newline']

            output_text += self.settings['newline']

        return output_text
