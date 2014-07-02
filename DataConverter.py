# -*- coding: utf-8 -*-
"""
DataConverter package for Sublime Text
https://github.com/fitnr/SublimeDataConverter

Freely adapted from Mr. Data Converter: http://shancarter.com/data_converter/
"""

import sublime
import sublime_plugin
import csv
import os
import re
try:
    import io
except Exception as e:
    import StringIO as io


# Borrowed from Apply Syntax
def sublime_format_path(pth):
    m = re.match(r"^([A-Za-z]{1}):(?:/|\\)(.*)", pth)
    if sublime.platform() == "windows" and m is not None:
        pth = m.group(1) + "/" + m.group(2)
    return pth.replace("\\", "/")


class DataConverterCommand(sublime_plugin.TextCommand):

    def run(self, edit, **kwargs):
        try:
            self.get_settings(kwargs)
        except Exception as e:
            print("DataConverter: error fetching settings. Did you specify a format?", e)
            return

        if self.view.sel()[0].empty():
            self.view.sel().add(sublime.Region(0, self.view.size()))
            deselect_flag = True

        for sel in self.view.sel():
            selection = self.view.substr(sel)
            sample = selection[:1024]

            # CSV dialect
            if not self.dialect:
                self.dialect = self.sniff(sample)

            print('DataConverter: using dialect', self.dialect)
            
            headers = self.assign_headers(sample, self.dialect)
            #  This also assigns types (for typed formats)
            data = self.import_csv(selection, headers, self.dialect)

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

        # The format key in .sublime-commands must match the name of the function we want to call.
        self.converter = getattr(self, kwargs['format'])

        # This will be set later on, in the converter function
        self.syntax = None

        self.settings = sublime.load_settings('DataConverter.sublime-settings')

        # Whitespace
        # Combine headers for certain formats
        no_space_formats = [
            'actionscript',
            'javascript',
            'mysql',
            'xml',
            'xml_properties',
            'yaml'
        ]
        mergeheaders = kwargs['format'] in no_space_formats
        self.settings.set('mergeheaders', mergeheaders)

        # Typing
        untyped_formats = [
            "html",
            "jira",
            "json",
            "json_columns",
            "json_rows",
            "text_table",
            "wiki"
            "xml",
            "xml_properties",
            "yaml"
        ]
        # Don't like having 'not' in this expression, but it makes more sense to use 'typed' from here on out
        # And it's less error prone to use the (smaller) list of untyped formats
        typed = kwargs['format'] not in untyped_formats
        self.settings.set('typed', typed)

        # New lines
        self.newline = self.settings.get('line_sep', False)
        if self.newline is False:
            self.newline = os.linesep

        # Indentation
        if (self.view.settings().get('translate_tabs_to_spaces')):
            self.indent = " " * int(self.view.settings().get('tab_size', 4))
        else:
            self.indent = "\t"

        # HTML characters
        self.html_utf8 = self.settings.get('html_utf8', True)

        if (self.settings.get('use_dialect')):
            self.dialect = self.set_dialect()
        else:
            self.dialect = None

    def set_dialect(self):
        dialectname = self.settings.get('use_dialect')
        try:
            csv.get_dialect(dialectname)
            return dialectname
        except Exception:
            user_dialects = self.settings.get('dialects')

        try:
            csv.register_dialect(dialectname, **user_dialects[dialectname])
            print("DataConverter: Using custom dialect", dialectname)
            return dialectname

        except Exception:
            print("DataConverter: Couldn't register custom dialect named", dialectname)
            return None

    def sniff(self, sample):
        try:
            dialect = csv.Sniffer().sniff(sample)
            csv.register_dialect('sniffed', dialect)
            print('DataConverter is using this delimiter:', dialect.delimiter)
            return 'sniffed'

        except Exception as e:
            print("DataConverter had trouble sniffing:", e)

            delimiter = self.settings.get('delimiter', ',')

            print('DataConverter: Using the default delimiter: "'+ delimiter +'"')
            print('DataConverter: You can change the default delimiter in the settings file.')

            delimiter = bytes(delimiter, 'utf-8')  # dialect definition takes a 1-char bytestring

            try:
                csv.register_dialect('barebones', delimiter=delimiter)
                return 'barebones'

            except Exception as e:
                return 'excel'
 
    def assign_headers(self, sample, dialect):
        '''Mess with headers, merging and stripping as needed.'''
        delimiter = csv.get_dialect(dialect).delimiter
        firstrow = sample.splitlines().pop(0).split(delimiter)
        header_setting = self.settings.get('headers')

        if header_setting is True:
            self.settings.set('has_header', True)

        # Using ['val1', 'val2', ...] if no headers
        elif header_setting is 'never':
            self.settings.set('has_header', False)

        else:
            # If not told to try definitely use headers or definitely not, we sniff for them.
            # Sniffing isn't perfect, especially with short data sets and strange delimiters
            try:
                sniffed_headers = csv.Sniffer().has_header(sample)

                if sniffed_headers:
                    self.settings.set('has_header', True)
                    print("DataConverter: CSV Sniffer found headers")
                else:
                    self.settings.set('has_header', False)
                    print("DataConverter: CSV Sniffer didn't find headers")

            except Exception:
                print("DataConverter: CSV module had trouble sniffing for headers. Assuming they exist.")
                print("DataConverter: Set 'headers = false' in the settings to disable.")
                self.settings.set('has_header', True)


        if self.settings.get('has_header', True):
            headers = firstrow
        else:
            headers = ["val" + str(x) for x in range(len(firstrow))]

        return self.format_headers(headers)

    def format_headers(self, headers):
        # Replace spaces in the header names for some formats.
        if self.settings.get('mergeheaders', False) is True:
            hj = self.settings.get('header_joiner', '_')
            headers = [x.replace(' ', hj) for x in headers]

        if self.settings.get('strip_quotes', True):
            headers = [j.strip('"\'') for j in headers]

        return headers

    def import_csv(self, selection, headers, dialect):
        # Remove header from entries that came with one.
        if self.settings.get('has_header', False) is True:
            selection = selection[selection.find(self.newline):]

        csvIO = io.StringIO(selection)

        reader = csv.DictReader(
            csvIO,
            fieldnames=headers,
            dialect=dialect)

        if self.settings.get('typed', False) is True:
            # Another reader for checking field types.
            typerIO = io.StringIO(selection)
            typer = csv.DictReader(typerIO, fieldnames=headers, dialect=dialect)
            self.types = self.parse(typer, headers)

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
            sublime.load_resource(new_syntax)
            self.view.set_syntax_file(new_syntax)

    # data type parser
    # ==================
    def parse(self, reader, headers):
        """ Return a list containing a best guess for the types of data in each column. """
        output_types, types = [], []

        for n in range(10):
            try:
                row = next(reader)
            except:
                print('Error parsing')
                break

            tmp = []

            for h in headers:
                typ = self.get_type(row[h])
                tmp.append(typ)

            types.append(tmp)

        #rotate the array
        types = list(zip(*types))

        for header, type_list in zip(headers, types):
            if str in type_list:
                output_types.append(str)
            elif float in type_list:
                output_types.append(float)
            else:
                output_types.append(int)

        print('DataConverter found these output types:', output_types)
        return output_types

    def get_type(self, datum):
        """ Select a data type from a (string) input"""
        try:
            int(datum)
            return int
        except:
            try:
                float(datum)
                return float
            except:
                return str

    # Converters
    # ==========

    # Note that converters should assign a syntax file path to self.syntax.

    def type_loop(self, row, headers, formt, nulltxt='null'):
        """
        Helper loop for checking types as we write out a row.
        Strings get quoted, floats and ints don't.
        row is a dictionary returned from DictReader
        Returns a line of code formatted with `formt` (e.g. "{0}=>{1}, ")

        """
        out = ''

        for key, typ in zip(headers, self.types):
            if row[key] is None:
                txt = nulltxt
            elif typ == str:
                txt = '"' + row[key] + '"'
            else:
                txt = row[key]

            out += formt.format(key, txt)
        return out

    def actionscript(self, data):
        """Actionscript converter"""

        self.set_syntax('ActionScript')

        output = "["

        #begin render loops
        for row in data:
            output += "{"
            output += self.type_loop(row, data.fieldnames, '{0}:{1},')

            output = output[0:-1] + "}" + "," + self.newline

        return output[:-2] + "];"

    # ASP / VBScript
    def asp(self, data):
        self.set_syntax('ASP')
        #comment, comment_end = "'", ""
        output, r = "", 0

        for row in data:

            for c, key, item_type in zip(range(len(data.fieldnames)), data.fieldnames, self.types):
                if item_type == str:
                    row[key] = '"' + (row[key] or "") + '"'
                if item_type is None:
                    row[key] = 'null'

                output += 'myArray({0},{1}) = {2}'.format(c, r, row[key] + self.newline)
            r = r + 1

        dim = 'Dim myArray({0},{1}){2}'.format(c, r - 1, self.newline)

        return dim + output

    def tr(self, row):
        """Helper for HTML converter"""
        return "{i}{i}<tr>{n}" + row + "{i}{i}</tr>{n}"

    def html(self, data):
        """HTML Table converter.
        We use {i} and {n} as shorthand for self.indent and self.newline."""

        self.set_syntax('HTML')
        thead, tbody = "", ""

        # Render the table head, if there is one
        if self.settings.get('has_header') is True:
            for header in data.fieldnames:
                thead += '{i}{i}{i}<th>' + header + '</th>{n}'

            thead = '{i}<thead>{n}' + self.tr(thead) + '</thead>{n}'
        else:
            thead = ''

        # Render table rows
        for row in data:
            rowText = ""

            for key in data.fieldnames:
                rowText += '{i}{i}{i}<td>' + (row[key] or "") + '</td>{n}'

            tbody += self.tr(rowText)

        table = "<table>{n}" + thead
        table += "{i}<tbody>{n}" + tbody + "{i}</tbody>{n}</table>"

        if self.html_utf8:
            return table.format(i=self.indent, n=self.newline)
        else:
            return table.format(i=self.indent, n=self.newline).encode('ascii', 'xmlcharrefreplace')

    def gherkin(self, data):
        '''Cucumber/Gherkin converter'''
        self.set_syntax('Cucumber', 'Cucumber Steps')
        output = "|"

        for header in data.fieldnames:
            output += header + "\t|"

        output += self.newline

        for row in data:
            output += "|" + self.type_loop(row, data.fieldnames, "{1}\t|", 'nil') + self.newline

        return output

    def javascript(self, data):
        """JavaScript object converter"""

        self.set_syntax('JavaScript')
        output = 'var dataConverter = [' + self.newline

        for row in data:
            output += self.indent + "{" + self.type_loop(row, data.fieldnames, '{0}: {1}, ')
            output = output[:-2] + "}," + self.newline

        return output[:-2] + self.newline + '];'

    def jira(self, data):
        sep = '|'
        output = (sep * 2) + (sep * 2).join(data.fieldnames) + (sep * 2) + self.newline

        for row in data:
            output += sep + sep.join(row.values()) + sep + self.newline

        return output

    def json(self, data):
        """JSON properties converter"""
        import json
        self.set_syntax('JavaScript', 'JSON')

        return json.dumps([row for row in data])

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
        return json.dumps(colDict)

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

        return json.dumps(rowArrays)

    def mysql(self, data):
        """MySQL converter
        We use {i} and {n} as shorthand for self.indent and self.newline."""

        self.set_syntax('SQL')

        table = 'DataConverter'

        # CREATE TABLE statement
        create = 'CREATE TABLE ' + table + '({n}'
        create += self.indent + "id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,{n}"

        # INSERT TABLE Statement
        insert = 'INSERT INTO ' + table + " {n}{i}("

        # VALUES list
        values = "VALUES" + self.newline

        # Loop through headers
        for header, typ in zip(data.fieldnames, self.types):
            if typ == str:
                typ = 'VARCHAR(255)'
            elif typ == float:
                typ = 'FLOAT'
            elif typ == int:
                typ = 'INT'

            insert += header + ","

            create += '{i}' + header + " " + typ + "," + self.newline

        create = create[:-2] + '{n}'  # Remove the comma and newline
        create += ") CHARACTER SET utf8;{n}"

        insert = insert[:-1] + ") {n}"

        for row in data:
            values += self.indent + "("
            values += self.type_loop(row, data.fieldnames, formt='{1},', nulltxt='NULL')

            values = values[:-1] + '),' + self.newline

        output = create + insert + values[:-2] + ';'
        return output.format(i=self.indent, n=self.newline)

    def perl(self, data):
        """Perl converter"""
        self.set_syntax('Perl')
        output = "["

        for row in data:
            output += "{"
            output += self.type_loop(row, data.fieldnames, '"{0}"=>{1}, ', nulltxt='undef')

            output = output[:-2] + "}," + self.newline

        return output[:-2] + "];"

    def php(self, data, array_open, array_close):
        """General PHP Converter"""
        self.set_syntax('PHP')
        #comment, comment_end = "//", ""

        output = "$DataConverter = " + array_open + self.newline

        for row in data:
            output += self.indent + array_open
            output += self.type_loop(row, data.fieldnames, '"{0}"=>{1}, ')

            output = output[:-2] + array_close + "," + self.newline

        return output[:-1] + self.newline + array_close + ";"

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
            for k, t in zip(data.fieldnames, self.types):
                if t == int:
                    outrow[k] = int(row[k])
                elif t == float:
                    outrow[k] = float(row[k])
                else:
                    outrow[k] = row[k]
            fields.append(outrow)

        return repr(fields)

    def python_list(self, data):
        """Python list of lists converter"""
        self.set_syntax('Python')
        fields = []
        for row in data:
            outrow = []
            for k, t in zip(data.fieldnames, self.types):
                if t == int:
                    outrow.append(int(row[k]))
                elif t == float:
                    outrow.append(float(row[k]))
                else:
                    outrow.append(row[k])
            fields.append(outrow)
        return '# headers = ' + repr(data.fieldnames) + self.newline + repr(fields)

    def ruby(self, data):
        """Ruby converter"""
        self.set_syntax('Ruby')
        #comment, comment_end = "#", ""
        output = "["

        for row in data:
            output += "{"
            output += self.type_loop(row, data.fieldnames, '"{0}"=>{1}, ', nulltxt='nil')

            output = output[:-2] + "}," + self.newline

        return output[:-2] + "];"

    def wiki(self, data):
        '''Wiki table converter'''
        # self.set_syntax('Text', 'Plain text')
        headsep, colsep = '!', '|'

        output = '{| class="wikitable"' + self.newline
        output += headsep + (headsep * 2).join(data.fieldnames) + self.newline
        
        for row in data:
            output += '|-' + self.newline
            output += colsep + (colsep * 2).join(row.values()) + self.newline

        return output + '|}'

    def xml(self, data):
        """XML Nodes converter"""
        self.set_syntax('XML')
        output_text = '<?xml version="1.0" encoding="UTF-8"?>{n}<rows>{n}'

        for row in data:
            output_text += '{i}<row>{n}'
            for header in data.fieldnames:
                item = row[header] or ""
                output_text += '{i}{i}<{1}>{0}</{1}>{n}'.format(item, header, i=self.indent, n=self.newline)

            output_text += "{i}</row>{n}"

        output_text += "</rows>"

        return output_text.format(i=self.indent, n=self.newline).encode('ascii', 'xmlcharrefreplace').decode('ascii', 'xmlcharrefreplace')

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

        return output_text.format(i=self.indent, n=self.newline).encode('ascii', 'xmlcharrefreplace').decode('ascii', 'xmlcharrefreplace')

    def xml_illustrator(self, data):
        '''Convert to Illustrator XML format'''
        self.set_syntax('XML')

        output = '<?xml version="1.0" encoding="utf-8"?>' + '{n}'
        output += '<!DOCTYPE svg PUBLIC "-//W3C//DTD SVG 20001102//EN"    "http://www.w3.org/TR/2000/CR-SVG-20001102/DTD/svg-20001102.dtd" [' + '{n}'
        output += '{i}'+'<!ENTITY ns_graphs "http://ns.adobe.com/Graphs/1.0/">' + '{n}'
        output += '{i}'+'<!ENTITY ns_vars "http://ns.adobe.com/Variables/1.0/">' + '{n}'
        output += '{i}'+'<!ENTITY ns_imrep "http://ns.adobe.com/ImageReplacement/1.0/">' + '{n}'
        output += '{i}'+'<!ENTITY ns_custom "http://ns.adobe.com/GenericCustomNamespace/1.0/">' + '{n}'
        output += '{i}'+'<!ENTITY ns_flows "http://ns.adobe.com/Flows/1.0/">' + '{n}'
        output += '{i}'+'<!ENTITY ns_extend "http://ns.adobe.com/Extensibility/1.0/">' + '{n}'
        output += ']>' + '{n}'
        output += '<svg>' + '{n}'
        output += '<variableSets  xmlns="&ns_vars;">' + '{n}'
        output += '{i}'+'<variableSet  varSetName="binding1" locked="none">' + '{n}'
        output += '{i}{i}'+'<variables>' + '{n}'

        for header in data.fieldnames:
            output += ('{i}' * 3) + '<variable varName="' + header + '" trait="textcontent" category="&ns_flows;"></variable>' + '{n}'

        output += '{i}{i}'+'</variables>' + '{n}'
        output += '{i}{i}'+'<v:sampleDataSets  xmlns:v="http://ns.adobe.com/Variables/1.0/" xmlns="http://ns.adobe.com/GenericCustomNamespace/1.0/">' + '{n}'

        for row in data:
            output += ('{i}' * 3) + '<v:sampleDataSet dataSetName="' + row[data.fieldnames[0]] + '">' + '{n}'

            for field in data.fieldnames:
                output += ('{i}' * 4) + '<' + field + '>' + '{n}'          
                output += ('{i}' * 5) + '<p>' + row[field] + '</p>' + '{n}'
                output += ('{i}' * 4) + '</' +  field + '>' + '{n}'

            output += ('{i}' * 3) + '</v:sampleDataSet>' + '{n}'

        output += '{i}{i}' + '</v:sampleDataSets>' + '{n}'
        output += '{i}' + '</variableSet>' + '{n}'
        output += '</variableSets>' + '{n}'
        output += '</svg>' + '{n}'

        return output.format(i=self.indent, n=self.newline)

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
                except:
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
        return output_text.format(n=self.newline)

    def yaml(self, data):
        '''YAML Converter'''

        #  Set the syntax of the document.
        #  In ST2 the syntax of this line is different
        self.set_syntax('YAML')

        #  The DataConverterCommand has two useful values
        #  for formatting text: self.newline and self.indent
        #  They respect the user's text settings
        output_text = "---" + self.newline

        #  data is a csv.reader object
        #  We use the `.fieldnames` parameter to keep header names straight
        #  For typed formats requiring, self.types is a list of the sniffed Python types of each column
        for row in data:
            output_text += "-" + self.newline
            for header in data.fieldnames:
                try:
                    output_text += "  " + header + ": " + row[header] + self.newline
                except Exception:
                    pass

            output_text += self.newline

        return output_text
