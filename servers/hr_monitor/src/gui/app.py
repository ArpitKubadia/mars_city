#!/usr/bin/env python
# -*- coding: utf-8 -*-
# generated by wxGlade 0.6.5 on Mon Sep  2 12:11:11 2013

import wx
from MainFrame import MainFrame


class HRMonitorGui(wx.App):
    def OnInit(self):
        wx.InitAllImageHandlers()
        mainFrame = MainFrame(None, -1, "")
        self.SetTopWindow(mainFrame)
        mainFrame.Show()
        return 1

# end of class HRMonitorGui

if __name__ == "__main__":
    app = HRMonitorGui(0)
    app.MainLoop()
