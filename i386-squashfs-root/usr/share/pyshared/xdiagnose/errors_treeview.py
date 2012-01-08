#!/usr/bin/env python

# example basictreeview.py

from gi.repository import Gtk

class ErrorsTreeView:

    def __init__(self, data=[]):
        # Create a new window
        self.window = Gtk.Window()
        self.window.set_title("Xorg Error Messages")
        self.window.set_size_request(500, 200)
        self.window.connect("delete_event", self.close)

        # create a TreeStore with one string column to use as the model
        self.treestore = Gtk.TreeStore(str)

        # we'll add some data now - 4 rows with 3 child rows each
        for errormsg in data:
            piter = self.treestore.append(None, [errormsg])
            #for child in range(3):
            #    self.treestore.append(piter, ['child text'])

        # create the TreeView using treestore
        self.treeview = Gtk.TreeView()
        self.treeview.set_model(self.treestore)

        # create the TreeViewColumn to display the data
        self.tvcolumn = Gtk.TreeViewColumn('Error Message')

        # add tvcolumn to treeview
        self.treeview.append_column(self.tvcolumn)

        # create a CellRendererText to render the data
        self.cell = Gtk.CellRendererText()

        # add the cell to the tvcolumn and allow it to expand
        self.tvcolumn.pack_start(self.cell, True)

        # set the cell "text" attribute to column 0 - retrieve text
        # from that column in treestore
        self.tvcolumn.add_attribute(self.cell, 'text', 0)

        # make it searchable
        self.treeview.set_search_column(0)

        # Allow sorting on the column
        self.tvcolumn.set_sort_column_id(0)

        # Allow drag and drop reordering of rows
        self.treeview.set_reorderable(True)

        self.window.add(self.treeview)
        self.window.show_all()

    # close the window
    def close(self, widget, event, data=None):
        self.window.destroy()
        return False

if __name__ == "__main__":
    tvexample = ErrorsTreeView()
    Gtk.main()
