from ..overrides import override
from ..importer import modules

Dee = modules['Dee']._introspection_module
from gi.repository import GLib

__all__ = []

class RowWrapper:
    def __init__ (self, model, itr):
        self.model = model
        self.itr = itr
    
    def __getitem__ (self, column):
        return self.model.get_value(self.itr, column)
    
    def __setitem__ (self, column, val):
        self.model.set_value (self.itr, column, val)
    
    def __iter__ (self):
        for column in range(self.model.get_n_columns()):
            yield self.model.get_value (self.itr, column)
    
    def __len__ (self):
        return self.model.get_n_columns()
    
    def __str__ (self):
        return "(%s)" % ", ".join(map(str,self))
    
    def __eq__ (self, other):
        if not isinstance (other, RowWrapper):
            return False
        if self.model != other.model:
            return False
        return self.itr == other.itr

class Model(Dee.Model):

    def __init__(self):
        Dee.Model.__init__(self)

    def set_schema (self, *args):
        self.set_schema_full (tuple(args), len(args))
    
    def _build_row (self, args):
        result = []
        for i, arg in enumerate(args):
            if isinstance(arg, GLib.Variant):
                result.append(arg)
            else:
                result.append(GLib.Variant(self.get_column_schema(i), arg))
        return tuple(result)
    
    def prepend (self, *args):
        return self.prepend_row (self._build_row(args))
    
    def append (self, *args):
        return self.append_row (self._build_row(args))
    
    def insert (self, pos, *args):
        return self.insert_row (pos, self._build_row(args))
    
    def insert_before (self, iter, *args):
        return self.insert_row_before (iter, self._build_row(args))
    
    def get_schema (self):
        return Dee.Model.get_schema(self)[0]
    
    def get_value (self, itr, column):
        return Dee.Model.get_value (self, itr, column).unpack()
    
    def set_value (self, itr, column, value):
        var = GLib.Variant (self.get_column_schema(column), value)
        if isinstance (itr, int):
            itr = self.get_iter_at_row(itr)
        Dee.Model.set_value (self, itr, column, var)
    
    def __getitem__ (self, itr):
        if isinstance (itr, int):
            itr = self.get_iter_at_row(itr)
        return RowWrapper(self, itr)
    
    def __setitem__ (self, itr, row):
        max_col = self.get_n_columns ()
        for column, value in enumerate (row):
            if column >= max_col:
                raise IndexError, "Too many columns in row assignment: %s" % column
            self.set_value (itr, column, value)
    
    def get_row (self, itr):
        return self[itr]
    
    def __iter__ (self):
        itr = self.get_first_iter ()
        last = self.get_last_iter ()
        while itr != last:
            yield self.get_row(itr)
            itr = self.next(itr)
        raise StopIteration
    
    def __len__ (self):
        return self.get_n_rows()
        
        

Model = override(Model)
__all__.append('Model')


