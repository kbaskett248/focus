from abc import abstractmethod
import logging

import sublime

from .metaclasses import MiniPluginMeta
from .code_blocks import CodeBlock
from .compatibility import FSCompatibility, FocusCompatibility
from ..tools import scope_from_view, get_member_region

logger = logging.getLogger(__name__)
logger.setLevel('DEBUG')


def get_mt_view(view):
    return MTView.get_mt_view(view)


class MTView(object, metaclass=MiniPluginMeta):
    """docstring for MTView"""

    Views = {}

    def __new__(cls, view):
        if cls.valid_view(view):
            return super(MTView, cls).__new__(cls)
        else:
            raise ViewTypeException(view, cls)

    def __init__(self, view):
        super(MTView, self).__init__()
        MTView.Views[self.__class__.view_key(view)] = self
        self.view = view

    @classmethod
    def get_mt_view(cls, view):
        v = None
        try:
            v = cls.Views[cls.view_key(view)]
        except KeyError:
            for c in cls.get_plugins():
                try:
                    v = c(view)
                    v.view = view
                except ViewTypeException:
                    continue
                else:
                    break
            else:
                raise ViewTypeException(view)
        finally:
            return v

    @classmethod
    @abstractmethod
    def valid_view(cls, view):
        pass

    @classmethod
    def view_key(cls, view):
        return (view.id(), scope_from_view(view))

    def get_contents(self):
        return self.view.substr(sublime.Region(0, self.view.size()))

    def get_line(self, point):
        """
        Returns a tuple of the span of the line or lines at the specified point
        and the contents of those lines.

        Keyword arguments:
        point - Either an int representing a point in the file or a tuple
            representing a selection in the file.
        """
        if isinstance(point, int):
            line = self.view.line(point)
        else:
            line = self.view.line(point[0]).cover(self.view.line(point[1]))

        return ((line.begin(), line.end()), self.view.substr(line))

    def get_lines_iterator(self, skip_blanks=False):
        """
        Creates an iterator that returns the lines of a file or view.
        """

        start = 0
        size = self.view.size()

        while start <= size:
            line_reg = self.view.line(start)
            if (not skip_blanks) or (line_reg.size() > 1):
                yield self.view.substr(line_reg)
            start = line_reg.end() + 1

    def get_lines_from_iterator(self, point, reverse=False, skip_blanks=False):
        """
        Creates an iterator that returns the lines of a file or view from the
        line containing the specified point.

        Keyword arguments:
        reverse - If false, return the lines from the line containing the
            specified point to the end. If True, return the lines from the
            line containing the specified point to the beginning.
        skip_blanks - If true, do not return empty lines.

        """
        start = point
        if reverse:
            while start > 0:
                line_reg = self.view.line(start)
                if (not skip_blanks) or (line_reg.size() > 1):
                    yield self.view.substr(line_reg)
                start = line_reg.begin() - 1
        else:
            size = self.view.size()
            while start <= size:
                line_reg = self.view.line(start)
                if (not skip_blanks) or (line_reg.size() > 1):
                    yield self.view.substr(line_reg)
                start = line_reg.end() + 1

    def _extract_entity(self, extract_func, point):
        if point is None:
            sel = self.view.sel()[0]
            point = (sel.begin(), sel.end())
        elif isinstance(point, sublime.Region):
            point = (point.begin(), point.end())

        return super(MTView, self)._extract_entity(extract_func, point)


class FocusView(MTView, FocusCompatibility):
    """docstring for FocusView"""

    @classmethod
    def valid_view(cls, view):
        return scope_from_view(view) == 'source.focus'

    def get_member_region(self, point=None):
        if point is None:
            point = self.view.sel()[0].begin()
        return get_member_region(self.view, point)

    def get_codeblock(self, point=None):
        if point is None:
            point = self.view.sel()[0].begin()
        return CodeBlock(self.view, point)

    def extract_fs_function(self, point=None):
        return super(FocusView, self).extract_fs_function(point)

    def extract_focus_function(self, point=None):
        return super(FocusView, self).extract_focus_function(point)

    def extract_alias(self, point=None):
        return super(FocusView, self).extract_alias(point)

    def get_locals(self, only_undocumented=False, with_documentation=False):
        if with_documentation:
            pass
        else:
            used_locals = set()

            if only_undocumented:
                locals_sections = [sublime.Region(r[0][0], r[0][1]) for r in
                                   self.get_translator_sections('Locals')]
                documented_locals = set()

            for r in self.view.find_by_selector('variable.other.local.focus'):
                local = self.view.substr(r)
                used_locals.add(local)
                if only_undocumented:
                    for ls in locals_sections:
                        if ls.contains(r):
                            documented_locals.add(local)
                            break

            logger.debug('Locals used in file: %s', used_locals)

            if only_undocumented:
                used_locals = used_locals - documented_locals
                logger.debug('Undefined Locals in file: %s', used_locals)

            used_locals = list(used_locals)
            used_locals.sort()

        return used_locals


class FSView(MTView, FSCompatibility):
    """docstring for FSView"""

    @classmethod
    def valid_view(cls, view):
        return scope_from_view(view) == 'source.fs'

    def get_member_region(self, point=None):
        if point is None:
            point = self.view.sel()[0].begin()
        return get_member_region(self.view, point)

    def get_codeblock(self, point=None):
        if point is None:
            point = self.view.sel()[0].begin()
        return CodeBlock(self.view, point)

    def extract_fs_function(self, point=None):
        return super(FSView, self).extract_fs_function(point)


class ViewTypeException(Exception):
    """docstring for ViewTypeException"""

    def __init__(self, view, view_type=None):
        super(ViewTypeException, self).__init__()
        self.view = view
        self.view_type = view_type

        if self.view.file_name() is not None:
            name = " ({0})".format(self.view.file_name())
        elif self.view.name() is not None:
            name = " ({0})".format(self.view.name())
        else:
            name = ""

        if view_type is not None:
            self.description = (
                "View {id}{name} is not a valid instance of "
                "View Type {type}").format(id=self.view.id(),
                                           name=name,
                                           type=self.view_type.__name__)
        else:
            self.description = (
                "View {id}{name} is not a valid View Type").format(
                    id=self.view.id(), name=name)
