"""module with example wx.grid.Grid."""
import wx
import wx.grid


class MyFrame(wx.Frame):
    """MyFrame example class."""

    def __init__(self, parent, title: str) -> None:
        super(MyFrame, self).__init__(parent, title=title, size=(400, 300))

        panel = wx.Panel(self)
        self.grid = wx.grid.Grid(panel)

        sample_data_as_list_of_dicts = [{"id": "pkg1",  "description": "Libreria Core del sistema", "name": "Pacchetto Alpha"}]

        column_names_in_order = ['id', 'name', 'description']

        num_rows = len(sample_data_as_list_of_dicts)
        num_cols = len(column_names_in_order)

        self.grid.CreateGrid(num_rows, num_cols)

        for c_idx, col_name in enumerate(column_names_in_order):
            self.grid.SetColLabelValue(c_idx, col_name)

        for r_idx, row_dict in enumerate(sample_data_as_list_of_dicts):
            for c_idx, col_name in enumerate(column_names_in_order):
                cell_value = row_dict.get(col_name, "")
                self.grid.SetCellValue(r_idx, c_idx, str(cell_value))

        self.grid.AutoSizeColumns()

        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(self.grid, 1, wx.EXPAND | wx.ALL, 5)
        panel.SetSizerAndFit(sizer)

        self.Centre()
        self.Show(True)

if __name__ == '__main__':
    app = wx.App(False)
    frame = MyFrame(None, "Esempio wx.grid.Grid")
    app.MainLoop()