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
import StringIO

PACKAGES = sublime.packages_path()


class UnicodeDictReader(object):
    '''Adapted from:
    http://stackoverflow.com/questions/5478659/python-module-like-csv-dictreader-with-full-utf8-support'''

    def __init__(self, data, fieldnames, encoding='utf-8', **kwargs):
        self.reader = csv.DictReader(data, fieldnames=fieldnames, **kwargs)
        self.fieldnames = fieldnames
        self.encoding = encoding

    def __iter__(self):
        return self

    def next(self):
        row = self.reader.next()
    
        y = dict()
        for k, v in row.iteritems():
            if v is None:
                v = ""

            y[k] = v.decode(self.encoding)

        return y


class DataConverterCommand(sublime_plugin.TextCommand):

    def run(self, edit, **kwargs):
        try:
            self.get_settings(kwargs)
        except Exception as e:
            print "DataConverter: error fetching settings. Did you specify a format?", e
            return

        if self.view.sel()[0].empty():
            self.view.sel().add(sublime.Region(0, self.view.size()))
            deselect_flag = True

        for sel in self.view.sel():
            selection = self.view.substr(sel)
            sample = selection[:1024]

            # Allow for difference dialects in different selections
            if not self.dialect:
                self.dialect = self.sniff(sample)
           
            headers = self.assign_headers(sample, self.dialect)
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
            "yaml"
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
            self.indent = u" " * int(self.view.settings().get('tab_size', 4))
        else:
            self.indent = u"\t"

        # HTML characters
        self.html_utf8 = self.settings.get('html_utf8', False)

        # Optionally set a user-defined CSV dialect from settigns
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
            print("DataConverter: Trying to parse a user dialect")

        try:
            onechars = ['delimiter', 'escapechar', 'quotechar']

            for item in onechars:
                if item in user_dialects[dialectname]:
                    user_dialects[dialectname][item] = bytes(user_dialects[dialectname][item][0])

            csv.register_dialect(dialectname, **user_dialects[dialectname])
            print("DataConverter: Using custom dialect", dialectname)
            return dialectname

        except Exception:
            print("DataConverter: Couldn't register custom dialect named", dialectname)
            return None

    def sniff(self, sample):
        try:
            dialect = csv.Sniffer().sniff(sample)
            # csv.Sniffer returns dialect in a format register_dialect doesn't like!
            # Pretty annoying bug!
            dialect.delimiter = bytes(dialect.delimiter)
            dialect.quotechar = bytes(dialect.quotechar)
            csv.register_dialect('sniffed', dialect)
            print('DataConverter is using this delimiter:', dialect.delimiter)
            return 'sniffed'

        except Exception as e:
            print("DataConverter had trouble sniffing:", e)

            delimiter = self.settings.get('delimiter', ',')

            print('DataConverter: Using the default delimiter: "'+ delimiter +'"')
            print('DataConverter: You can change the default delimiter in the settings file.')

            delimiter = bytes(delimiter)  # dialect definition takes a 1-char bytestring

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

        selection = selection.encode('utf-8')
        csvIO = StringIO.StringIO(selection)

        reader = UnicodeDictReader(
            csvIO,
            encoding='utf-8',
            fieldnames=headers,
            dialect=dialect)

        if self.settings.get('typed', False) is True:
            # Another reader for checking field types.
            try:
                typerIO = StringIO.StringIO(selection)
                typer = csv.DictReader(typerIO, fieldnames=headers, dialect=dialect)
                self.types = self.parse(typer, headers)
            except:
                pass

        return reader

    def deselect(self):
        """Remove selection and place pointer at top of document (adapted from https://gist.github.com/1608283)."""
        top = self.view.sel()[0].a
        self.view.sel().clear()
        self.view.sel().add(sublime.Region(top, top))

    # data type parser
    # ==================

    def parse(self, reader, headers):
        """ Return a list containing a best guess for the types of data in each column. """
        output_types, types = [], []

        for n in range(10):
            try:
                row = reader.next()
            except:
                break

            tmp = []

            for h in headers:
                typ = self.get_type(row[h])
                tmp.append(typ)

            types.append(tmp)

        #rotate the array
        types = zip(*types)

        for header, type_list in zip(headers, types):
            if str in type_list:
                output_types.append(str)
            elif float in type_list:
                output_types.append(float)
            else:
                output_types.append(int)

        print 'DataConverter found these output types:', output_types
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
        Returns a line of code in format `formt` (e.g. "{0}=>{1}, ")

        """
        out = u''
        for key, typ in zip(headers, self.types):
            if row[key] is None:
                txt = nulltxt
            elif typ == str:
                txt = u'"' + row[key] + '"'
            else:
                txt = row[key]

            out += formt.format(key, txt)
        return out

    def actionscript(self, data):
        """Actionscript converter"""
        self.syntax = PACKAGES + '/ActionScript/ActionScript.tmLanguage'
        output = u"["

        for row in data:
            output += "{"
            output += self.type_loop(row, data.fieldnames, u'{0}:{1},')

            output = output[0:-1] + "}" + "," + self.newline

        return output[:-2] + "];"

    # ASP / VBScript
    def asp(self, data):
        self.syntax = PACKAGES + '/ASP/ASP.tmLanguage'
        #comment, comment_end = "'", ""
        output, r = u"", 0
        zipper = zip(range(len(data.fieldnames)), data.fieldnames, self.types)
        #print data.fieldnames, self.types

        for row in data:

            for c, key, item_type in zipper:

                if item_type == str:
                    row[key] = '"' + (row[key] or "") + '"'
                if item_type is None:
                    row[key] = 'null'

                output += u'myArray({0},{1}) = {2}'.format(c, r, row[key] + self.newline)
            r = r + 1

        dim = u'Dim myArray({0},{1}){2}'.format(c, r - 1, self.newline)

        return dim + output

    def tr(self, row):
        """Helper for HTML converter"""
        return "{i}{i}<tr>{n}" + row + "{i}{i}</tr>{n}"

    def html(self, data):
        """HTML Table converter"""
        self.syntax = PACKAGES + '/HTML/HTML.tmLanguage'
        thead, tbody = u"", u""

        # Render the table head, if there is one
        if self.settings.get('has_header') is True:
            for header in data.fieldnames:
                thead += u'{i}{i}{i}<th>' + header + '</th>{n}'

            thead = u'{i}<thead>{n}' + self.tr(thead) + '</thead>{n}'
        else:

            thead = ''

        # Render table rows
        for row in data:
            rowText = u""

            # Sadly, dictReader doesn't always preserve row order,
            # so we loop through the headers instead.
            for key in data.fieldnames:
                rowText += u'{i}{i}{i}<td>' + (row[key] or "") + u'</td>{n}'

            tbody += self.tr(rowText)

        table = u"<table>{n}" + thead
        table += u"{i}<tbody>{n}" + tbody + u"</tbody>{n}</table>"

        if self.html_utf8:
            return table.format(i=self.indent, n=self.newline)
        else:
            return table.format(i=self.indent, n=self.newline).encode('ascii', 'xmlcharrefreplace')

    def javascript(self, data):
        """JavaScript object converter"""
        self.syntax = PACKAGES + '/JavaScript/JavaScript.tmLanguage'
        output = u'var dataConverter = [' + self.newline

        for row in data:
            output += self.indent + "{" + self.type_loop(row, data.fieldnames, u'{0}: {1}, ')
            output = output[:-2] + "}," + self.newline

        return output[:-2] + self.newline + '];'

    def json(self, data):
        """JSON properties converter"""
        import json
        self.syntax = PACKAGES + '/JavaScript/JavaScript.tmLanguage'

        return json.dumps([row for row in data])

    def json_columns(self, data):
        """JSON Array of Columns converter"""
        import json
        self.syntax = PACKAGES + '/JavaScript/JavaScript.tmLanguage'
        colDict = {}

        for row in data:
            for key, item in row.iteritems():
                if key not in colDict:
                    colDict[key] = []
                colDict[key].append(item)
        return json.dumps(colDict)

    def json_rows(self, data):
        """JSON Array of Rows converter"""
        import json
        self.syntax = PACKAGES + '/JavaScript/JavaScript.tmLanguage'
        rowArrays = []

        for row in data:
            itemlist = []
            for item in row.itervalues():
                itemlist.append(item)
            rowArrays.append(itemlist)

        return json.dumps(rowArrays)

    def mysql(self, data):
        """MySQL converter"""
        self.syntax = PACKAGES + '/SQL/SQL.tmLanguage'

        table = u'DataConverter'

        # CREATE TABLE statement
        create = u'CREATE TABLE ' + table + '({n}'
        create += self.indent + u"id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,{n}"

        # INSERT TABLE Statement
        insert = u'INSERT INTO ' + table + " {n}{i}("

        # VALUES list
        values = u"VALUES" + self.newline

        # Loop through headers
        for header, typ in zip(data.fieldnames, self.types):
            if typ == str:
                typ = u'VARCHAR(255)'
            elif typ == float:
                typ = u'FLOAT'
            elif typ == int:
                typ = u'INT'

            insert += header + ","

            create += u'{i}' + header + " " + typ + "," + self.newline

        create = create[:-2] + '{n}'  # Remove the comma and newline
        create += u") CHARACTER SET utf8;{n}"

        insert = insert[:-1] + u") {n}"

        # loop through rows
        for row in data:
            values += self.indent + u"("
            values += self.type_loop(row, data.fieldnames, form=u'{1},', nulltxt='NULL')

            values = values[:-1] + u'),' + self.newline

        output = create + insert + values[:-2] + ';'
        return output.format(i=self.indent, n=self.newline)

    def perl(self, data):
        """Perl converter"""
        self.syntax = PACKAGES + '/Perl/Perl.tmLanguage'
        output = u"["

        for row in data:
            output += "{"
            output += self.type_loop(row, data.fieldnames, u'"{0}"=>{1}, ', nulltxt='undef')

            output = output[:-2] + "}," + self.newline

        return output[:-2] + "];"

    def php(self, data):
        """PHP converter"""
        self.syntax = PACKAGES + '/PHP/PHP.tmLanguage'
        #comment, comment_end = "//", ""
        output = u"$DataConverter = array(" + self.newline

        for row in data:
            output += self.indent + u"array("
            output += self.type_loop(row, data.fieldnames, u'"{0}"=>{1}, ')

            output = output[:-2] + u")," + self.newline

        return output[:-1] + self.newline + u");"

    def python_dict(self, data):
        """Python dict converter"""
        self.syntax = PACKAGES + '/Python/Python.tmLanguage'
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
        self.syntax = PACKAGES + '/Python/Python.tmLanguage'
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
        self.syntax = PACKAGES + '/Ruby/Ruby.tmLanguage'
        #comment, comment_end = "#", ""
        output = u"["

        for row in data:
            output += "{"
            output += self.type_loop(row, data.fieldnames, u'"{0}"=>{1}, ', nulltxt='nil')

            output = output[:-2] + "}," + self.newline

        return output[:-2] + "];"

    def xml(self, data):
        """XML Nodes converter"""
        self.syntax = PACKAGES + '/XML/XML.tmLanguage'
        output_text = u'<?xml version="1.0" encoding="UTF-8"?>{n}<rows>{n}'

        for row in data:
            output_text += u'{i}<row>{n}'
            for header in data.fieldnames:
                item = row[header] or ""
                output_text += u'{i}{i}<{1}>{0}</{1}>{n}'.format(item, header, i=self.indent, n=self.newline)

            output_text += u"{i}</row>{n}"

        output_text += u"</rows>"

        return output_text.format(i=self.indent, n=self.newline).encode('ascii', 'xmlcharrefreplace')

    def xml_properties(self, data):
        """XML properties converter"""
        self.syntax = PACKAGES + '/XML/XML.tmLanguage'
        output_text = u'<?xml version="1.0" encoding="UTF-8"?>{n}<rows>{n}'

        for row in data:
            row_list = []

            for header in data.fieldnames:
                item = row[header] or ""
                row_list.append(u'{0}="{1}"'.format(header, item))
                row_text = u" ".join(row_list)

            output_text += u"{i}<row " + row_text + "></row>{n}"

        output_text += u"</rows>"

        return output_text.format(i=self.indent, n=self.newline).encode('ascii', 'xmlcharrefreplace')

    def text_table(self, data):
        """text table converter"""
        self.syntax = PACKAGES + '/Text/Plain text.tmLanguage'
        output_text, divline, field_length, _data = u'|', u'+', {}, []

        _data = [row for row in data]

        for header in data.fieldnames:
            length = len(header) + 1  # Add 1 to account for end-padding

            for row in _data:
                try:
                    length = max(length, len(row[header]) + 1)
                except:
                    pass
            field_length[header] = length
            divline += '-' * (field_length[header] + 1) + '+'

            output_text += ' ' + header + ' ' * (field_length[header] - len(header)) + '|'

        divline += u'{n}'

        if self.settings.get('has_header', False):
            output_text = u'{0}{1}{{n}}{0}'.format(divline, output_text)
        else:
            output_text = divline

        for row in _data:
            row_text = u'|'

            for header in data.fieldnames:
                item = row[header] or ""
                row_text += u' ' + item + ' ' * (field_length[header] - len(item)) + '|'

            output_text += row_text + "{n}"

        output_text += divline
        return output_text.format(n=self.newline)

    def yaml(self, data):
        self.syntax = PACKAGES + '/YAML/YAML.tmLanguage'

        output_text = u"---" + self.newline

        for row in data:
            output_text += u"-" + self.newline
            for header in data.fieldnames:
                if row[header]:
                    output_text += "  " + header + ": " + row[header] + self.newline
            output_text += self.newline

        return output_text
