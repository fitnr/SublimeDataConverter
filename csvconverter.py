import sublime
import sublime_plugin
import csv
import os
import StringIO

"""
    # Actionscript
    def actionscript(self, datagrid):
        commentLine = "#"
        commentLineEnd = ""
        outputText = "["

        #begin render loops
        for row in self.datagrid:
            outputText += "{"
            for hType in headerTypes:

                if ((hType == "int") or (hType == "float")):
                    rowOutput = row or "null"
                else:
                    rowOutput = '"' + (row or "") + '"'

                outputText += (headerNames[j] + ":" + rowOutput)

            if (j < (numColumns-1)) {outputText + =","}
          }
            outputText += "}"
            if (i < (numRows-1)) {outputText += "," + self.newline}
        }
        outputText += "];"


        return outputText

    # ASP / VBScript
    def asp(self, datagrid):
        #inits...
        commentLine = "'"
        commentLineEnd = ""
        outputText = ""

        #begin render loop
        for row in datagrid:
            for (j=0; j < numColumns; j +  + )
            if ((headerTypes[j] == "int") or (headerTypes[j] == "float"))
              rowOutput = row[j] or "null"
            } else
              rowOutput = '"' + ( row[j] or "" ) + '"'
            }
            outputText += 'myArray(' + j + ',' + i + ') = ' + rowOutput + self.newline
          }
        }
        outputText = 'Dim myArray(' + (j-1) + ',' + (i-1) + ')' + self.newline + outputText
        return outputText
"""
"""
    #MYSQL
    def mysql(self, datagrid):
        #inits...
        commentLine = "/*"
        commentLineEnd = "*/"
        outputText = ""
        tableName = "MrDataConverter"

        #begin render loop
        outputText += 'CREATE TABLE ' + tableName + ' (' + self.newline
        outputText += self.indent + "id INT NOT NULL AUTO_INCREMENT PRIMARY KEY," + self.newline
        for (j=0; j < numColumns; j +  + )
            dataType = "VARCHAR(255)"
            if ((headerTypes[j] == "int") or (headerTypes[j] == "float"))
            dataType = headerTypes[j].toUpperCase()
          }
            outputText += self.indent + "" + headerNames[j] + " " + dataType
            if (j < numColumns - 1) {outputText += ","}
            outputText += self.newline
        }
        outputText += ');' + self.newline
        outputText += "INSERT INTO " + tableName + " " + self.newline + self.indent + "("
        for (j=0; j < numColumns; j +  + )
            outputText += headerNames[j]
            if (j < numColumns - 1) {outputText += ","}
        }
        outputText += ") " + self.newline + "VALUES " + self.newline
        for (i=0; i < numRows; i +  + )
            outputText += self.indent + "("
            for (j=0; j < numColumns; j +  + )
            if ((headerTypes[j] == "int") or (headerTypes[j] == "float"))
              outputText += datagrid[i][j] or "null"
            } else
              outputText += "'" + ( datagrid[i][j] or "" ) + "'"
            }

            if (j < numColumns - 1) {outputText += ","}
          }
            outputText += ")"
            if (i < numRows - 1) {outputText += "," + self.newline;}
        }
        outputText += ";"
        return outputText


    # PHP
    def php(self, datagrid):
        #inits...
        commentLine = "#"
        commentLineEnd = ""
        outputText = ""
        tableName = "MrDataConverter"

        #begin render loop
        outputText += "array(" + self.newline
        for (i=0; i < numRows; i +  + )
            row = datagrid[i]
            outputText += self.indent + "array("
            for (j=0; j < numColumns; j +  + )
            if ((headerTypes[j] == "int") or (headerTypes[j] == "float"))
              rowOutput = row[j] or "null"
            } else
              rowOutput = '"' + (row[j] or "") + '"'
            }
            outputText += ('"' + headerNames[j] + '"' + "=>" + rowOutput)
            if (j < (numColumns-1)) {outputText + =","}
          }
            outputText += ")"
            if (i < (numRows-1)) {outputText += "," + self.newline}
        }
        outputText += self.newline + ");"

        return outputText

    # Ruby
    def ruby(self, datagrid):
        #inits...
        commentLine = "#"
        commentLineEnd = ""
        outputText = ""
        tableName = "MrDataConverter"

        #begin render loop
        outputText += "["
        for (i=0; i < numRows; i +  + )
            row = datagrid[i]
            outputText += "{"
            for (j=0; j < numColumns; j +  + )
            if ((headerTypes[j] == "int") or (headerTypes[j] == "float"))
              rowOutput = row[j] or "nil"
            } else
              rowOutput = '"' + (row[j] or "") + '"'
            }
            outputText += ('"' + headerNames[j] + '"' + "=>" + rowOutput)
            if (j < (numColumns-1)) {outputText + =","}
          }
            outputText += "}"
            if (i < (numRows-1)) {outputText += "," + self.newline}
        }
        outputText += "];"

        return outputText


    # XML Nodes
    def xml(self, datagrid):
        #inits...
        commentLine = "<!--"
        commentLineEnd = "-->"
        outputText = ""

        #begin render loop
        outputText = '<?xml version="1.0" encoding="UTF-8"?>' + self.newline
        outputText += "<rows>" + self.newline
        for (i=0; i < numRows; i +  + )
            row = datagrid[i]
            outputText += self.indent + "<row>" + self.newline
            for (j=0; j < numColumns; j +  + )
            outputText += self.indent + self.indent + '<' + headerNames[j] + '>'
            outputText += row[j] or ""
            outputText += '</' + headerNames[j] + '>' + self.newline
          }
            outputText += self.indent + "</row>" + self.newline
        }
        outputText += "</rows>"

        return outputText
    # XML properties
    def xmlProperties(self, datagrid):
        #inits...
        commentLine = "<!--"
        commentLineEnd = "-->"
        outputText = ""

        #begin render loop
        outputText = '<?xml version="1.0" encoding="UTF-8"?>' + self.newline
        outputText += "<rows>" + self.newline
        for (i=0; i < numRows; i +  + )
            row = datagrid[i]
            outputText += self.indent + "<row "
            for (j=0; j < numColumns; j +  + )
            outputText += headerNames[j] + '='
            outputText += '"' + row[j] + '" '
          }
            outputText += "></row>" + self.newline
        }
        outputText += "</rows>"

        return outputText
"""


class CsvConvertCommand(sublime_plugin.TextCommand):

    def run(self, edit, **kwargs):
        self.formats = {
            "html": {'syntax': '../HTML/HTML.tmLanguage', 'function': self.html},
            "json": {'syntax': '../JavaScript/JavaScript.tmLanguage', 'function': self.json},
            "json (array of columns)": {'syntax': '../JavaScript/JavaScript.tmLanguage', 'function': self.jsonArrayCols},
            "json (array of rows)": {'syntax': '../JavaScript/JavaScript.tmLanguage', 'function': self.jsonArrayRows},
            "python": {'syntax': '../Python/Python.tmLanguage', 'function': self.python}
        }

        format = self.formats[kwargs['format']]
        converter = format['function']
        syntax = format['syntax']

        if (self.view.settings().get('translate_tabs_to_spaces')):
            self.indent = int(self.view.settings().get('tab_size', 4))
        else:
            self.indent = "\t"
            self.newline = "\n"

        if self.view.sel()[0].empty():
            self.view.sel().add(sublime.Region(0, self.view.size()))
        for sel in self.view.sel():
            datagrid = self.import_csv(self.view.substr(sel).encode('utf-8'))
            self.view.replace(edit, sel, converter(datagrid))

        self.view.set_syntax_file(syntax)

    def import_csv(self, selection):
        sample = selection[:1024]
        dialect = csv.Sniffer().sniff(sample)

        csvIO = StringIO.StringIO(selection)

        firstrow = sample.splitlines()[0].split(dialect.delimiter)

        if csv.Sniffer().has_header(sample):
            self.headers = firstrow
        else:
            self.headers = ["val" + str(x) for x in range(len(firstrow))]

        reader = csv.DictReader(
            csvIO,
            fieldnames=self.headers,
            dialect=dialect)

        return reader

    # HTML Table
    def html(self, datagrid):
        outputText = ""

        #begin render loop
        outputText += "<table>" + self.newline
        outputText += self.indent + "<thead>" + self.newline
        outputText += self.indent * 2
        outputText += "<tr>" + self.newline

        for header in self.headers:
            outputText += self.indent * 3
            outputText += '<th>' + header + '</th>'
            outputText += self.newline

        outputText += self.indent * 2
        outputText += "</tr>" + self.newline
        outputText += self.indent + "</thead>" + self.newline
        outputText += self.indent + "<tbody>" + self.newline

        for row in datagrid:
            outputText += self.indent * 2
            outputText += "<tr>" + self.newline

            for key, item in row.iteritems():
                outputText += self.indent * 3
                outputText += '<td>' + item + '</td>' + self.newline

            outputText += self.indent * 2
            outputText += "</tr>" + self.newline

        outputText += self.indent + "</tbody>" + self.newline
        outputText += "</table>"

        self.view.set_syntax_file('HTML/HTML.tmLanguage')
        return outputText

    # JSON properties
    def json(self, datagrid):
        import json
        return json.dumps([row for row in datagrid])

    # JSON Array of Columns
    def jsonArrayCols(self, datagrid):
        import json
        colDict = {}
        for row in datagrid:
            for key, item in row.iteritems():
                if key not in colDict:
                    colDict[key] = []
                colDict[key].append(item)
        return json.dumps(colDict)

    # JSON Array of Rows
    def jsonArrayRows(self, datagrid):
        import json
        rowArrays = []

        for row in datagrid:
            itemlist = []
            for item in row.itervalues():
                itemlist.append(item)
            rowArrays.append(itemlist)

        return json.dumps(rowArrays)

    # Python dict
    def python(datagrid):
        outDicts = []
        for row in datagrid:
            outDicts.append(row)
        return repr(outDicts)
