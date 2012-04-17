/* pil-to-drawable - python util to draw a pil to a widget
 * Copyright (C) 2001 Nathan Hurst
 *
 * This library is free software; you can redistribute it and/or
 * modify it under the terms of the GNU Library General Public
 * License as published by the Free Software Foundation; either
 * version 2 of the License, or (at your option) any later version.
 *
 * This library is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
 * Library General Public License for more details.
 *
 * You should have received a copy of the GNU Library General Public
 * License along with this library; if not, write to the
 * Free Software Foundation, Inc., 59 Temple Place - Suite 330,
 * Boston, MA 02111-1307, USA.
 */

#ifdef HAVE_CONFIG_H
#  include "config.h"
#endif

extern "C"{
#include <Python.h>
#include <gtk/gtk.h>
#include <gdk-pixbuf/gdk-pixbuf.h>
#include "pygtk/pygtk.h"
#include <stdio.h>
#include <assert.h>
}

extern "C"{
#include <Imaging.h>
}

static PyObject *_register_types(PyObject *self, PyObject *args) {
  static gboolean called = FALSE;

  if (!called) {
    called = TRUE;
  
  }
  Py_INCREF(Py_None);
  return Py_None;
}

static PyObject *paint_PIL_drawable(PyObject *self,PyObject *args) {
  long x,y,id;
  long src_x, src_y;
  Imaging im;

  PyObject *drawable, *gc;
  
  if (!PyArg_ParseTuple(args,"l(ll)(ll)O!O!",&id,
			&src_x,&src_y,&x,&y, 
			&PyGdkWindow_Type, &drawable,
			&PyGdkGC_Type, &gc)) {
    return NULL;
  }

  im = (Imaging)id;
  
  assert(im);
  
  int t = y, l = x;
#define min(a, b) ((a<b)?a:b)
  int w = (im->xsize) - src_x;
  int h = (im->ysize);
  assert(im->image32);
  if(((w > 0) && (h > 0))) {
    int row_width, next_row_width;
    int start_y = src_y, end_y = src_y;
    while(end_y < h) {
      start_y = end_y;
      assert(im->image32[start_y]);
      next_row_width = row_width = ((guchar*)im->image32[start_y+1]) - 
	((guchar*)im->image32[start_y]);
      
      do {
	end_y++;
	if(end_y >= h) break;
	next_row_width = ((guchar*)im->image32[end_y+1]) - 
	  ((guchar*)im->image32[end_y]);
      } while(next_row_width == row_width);
      
      GdkPixbuf* gpb = gdk_pixbuf_new_from_data((guchar*)im->image32[start_y],
						GDK_COLORSPACE_RGB,
						1,
						8,
						im->xsize,
						end_y - start_y, // height
						row_width,
						NULL,
						NULL);
      assert(gpb);
      
      GdkGC* gcp =  PyGdkGC_Get(gc);
      assert(gcp);
      GdkWindow* drawablep = PyGdkWindow_Get(drawable);
      assert(drawablep);
      
      gdk_pixbuf_render_to_drawable(gpb,
				    drawablep,
				    gcp,
				    0, 0,
				    l, t+start_y - src_y,
				    w,
				    end_y - start_y,
				    GDK_RGB_DITHER_NONE,
				    0,0);
      
      gdk_pixbuf_unref(gpb);
    }
  }
  Py_INCREF(Py_None);
  return Py_None;
}



static PyMethodDef pyartMethods[] = {
  { "_register_types", _register_types, 1 },
  { "pil2drawable", paint_PIL_drawable, METH_VARARGS },
  { NULL, NULL, 0 }
};

extern "C"{
/* a function to initialise the pygtk functions */
void init_pygtk2() { 
  PyObject *pygtk = PyImport_ImportModule("_gtk"); 
  if (pygtk != NULL) { 
    PyObject *module_dict = PyModule_GetDict(pygtk); 
    PyObject *cobject = PyDict_GetItemString(module_dict, "_PyGtk_API"); 
    if (PyCObject_Check(cobject)) 
      _PyGtk_API = (_PyGtk_FunctionStruct *)PyCObject_AsVoidPtr(cobject); 
    else { 
      Py_FatalError("could not find _PyGtk_API object"); 
      return; 
    } 
  } else { 
    Py_FatalError("could not import _gtk"); 
    return; 
  } 
}

void initpil2drawable() {
  PyObject *m, *d;
  
  m = Py_InitModule("pil2drawable", pyartMethods);
  
  init_pygtk2();
  gdk_rgb_init();
  
  if (PyErr_Occurred())
    Py_FatalError("can't initialise module pil2drawable");
}
}

