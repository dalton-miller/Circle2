/* -*- Mode: C; tab-width: 8; indent-tabs-mode: t; c-basic-offset: 8 -*- */
/*
 * Copyright (C) 2003 Imendio HB 
 *
 * This library is free software; you can redistribute it and/or
 * modify it under the terms of the GNU General Public License as
 * published by the Free Software Foundation; either version 2 of the
 * License, or (at your option) any later version.
 *
 * This library is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
 * General Public License for more details.
 *
 * You should have received a copy of the GNU General Public
 * License along with this library; if not, write to the
 * Free Software Foundation, Inc., 59 Temple Place - Suite 330,
 * Boston, MA 02111-1307, USA.
 */

#include <string.h>
#include <libgnomevfs/gnome-vfs.h>
#include <libgnomevfs/gnome-vfs-module.h>

/* this is from gnome-vfs-monitor-private.h */
void gnome_vfs_monitor_callback (GnomeVFSMethodHandle *method_handle,
                                 GnomeVFSURI *info_uri,
                                 GnomeVFSMonitorEventType event_type);


/* A fake node (file or directory) in our fake file system. */
typedef struct {
	GNode                   *gnode;
	gchar                   *name;
	gchar                   *content;
	gsize                    size;
	gboolean                 directory;
} FakeNode;

typedef struct {
	GnomeVFSFileInfoOptions  options;

	FakeNode                *fnode;

	gchar                   *str;
	gint                     len;
	gint                     bytes_written;
} FileHandle;

typedef struct {
	GnomeVFSFileInfoOptions  options;

	GNode                   *gnode;
	GNode                   *current_child;
} DirHandle; 

static GNode *root = NULL;
static GList *monitor_list = NULL;

static void
invoke_monitors (void)
{
    GList *l;

    //G_LOCK (monitor_list);
    for (l = monitor_list; l; l = l->next) {
	GnomeVFSURI *uri = l->data;

	gnome_vfs_monitor_callback ((GnomeVFSMethodHandle *) uri, uri,
				    GNOME_VFS_MONITOR_EVENT_CHANGED);
    }
    //G_UNLOCK (monitor_list);
}

static void
print_tree (GNode *node, gint depth)
{
	GNode    *n;
	FakeNode *file;
	gint      i;

	for (i = 0; i < depth; i++) {
		g_print ("  ");
	}

	n = node;
	while (n) {
		file = n->data;
	
		g_print ("%s\n", file->name);

		if (file->directory) {
			print_tree (n->children, depth + 1);
		} else {
			g_print ("[%s]\n", file->content);
		}

		n = n->next;
	}
}


/* Helper function that splits up a path into its components, removing any empty
 * parts at the start and end.
 */
static GList *
split_path (const gchar *path)
{
	gchar  *tmp;
	gchar **strv, **p;
	GList  *list = NULL;

	if (path[0] == '/') {
		path++;
	}
	
	tmp = g_strdup (path);

	if (tmp[strlen (tmp) - 1] == '/') {
		tmp[strlen (tmp) - 1] = '\0';
	}
	
	strv = g_strsplit (tmp, G_DIR_SEPARATOR_S, 0);

	p = strv;
	while (*p) {
		list = g_list_append (list, g_strdup (*p));
		p++;
	}
	
	g_strfreev (strv);
	
	return list;
}

static FakeNode *
get_fake_node_from_uri (const GnomeVFSURI *uri)
{
	const gchar  *tmp;
	GList        *list, *l;
	gchar        *part;
	GNode        *gnode, *found_gnode = NULL;
	FakeNode     *file;
	gchar        *path;

	tmp = gnome_vfs_uri_get_path (uri);
	if (!tmp || strcmp (tmp, "/") == 0) {
		/* Special case the root. */
		return root->data;
	}

	if (tmp[0] == '/') {
		tmp++;
	}

	//g_print ("GET FAKE %s\n", tmp);
	
	/* Split the path into separate components. */
	list = split_path (tmp);

	l = list;
	gnode = root->children;
	while (gnode) {
		part = l->data;
		file = gnode->data;

		//g_print ("FILE %s (compare to %s)\n", file->name, part); 
			 
		path = file->name;
		if (path[0] == '/') {
			path++;
		}
		
		if (strcmp (part, path) == 0) {
			l = l->next;
			if (!l) {
				found_gnode = gnode;
				break;
			}
			
			gnode = gnode->children;
			continue;
		} 

		gnode = gnode->next;
	}

	for (l = list; l; l = l->next) {
		g_free (l->data);
	}
	g_list_free (list);

	//g_print ("GOT FAKE %p\n", found_node ? found_node->data : NULL);

	return found_gnode ? found_gnode->data : NULL;
}

static FakeNode *
fake_node_new (const gchar *name, const gchar *content)
{
	FakeNode *file;

	file = g_new0 (FakeNode, 1);
	file->name = g_strdup (name);

	if (content) {
		file->content = g_strdup (content);
		file->size = strlen (content) + 1;
	}
	
	file->directory = FALSE;

	return file;
}

static void
init_fake_tree ()
{
	FakeNode *file;
	GNode    *documents;

	/* Create a fake directory structure. */

	file = fake_node_new ("<root>", NULL);
	root = g_node_new (file);
	file->gnode = root;
	file->directory = TRUE;

	file = fake_node_new ("documents", NULL);
	documents = g_node_append_data (root, file);
	file->gnode = documents;
	file->directory = TRUE;

	file = fake_node_new ("test.txt", "Test file\n");
	file->gnode = g_node_append_data (root, file);

	file = fake_node_new ("todo.txt", "Buy milk\nWash dishes\n");
	file->gnode = g_node_append_data (documents, file);
}

static void
free_fake_tree ()
{
	/* FIXME: Traverse and free the data... */

	root = NULL;
}

static FakeNode *
add_fake_node (GnomeVFSURI *uri, gboolean directory)
{
	GnomeVFSURI *parent_uri;
	FakeNode    *parent_file;
	const gchar *path, *name;
	FakeNode    *file;

	parent_uri = gnome_vfs_uri_get_parent (uri);
	parent_file = get_fake_node_from_uri (parent_uri);

	if (!parent_file) {
		return NULL;
	}
	
	path = gnome_vfs_uri_get_path (uri);
	name = strrchr (path, '/') + 1;

	g_print ("ADD FAKE: %s, dir: %d\n", name, directory);
	
	file = fake_node_new (name, NULL);

	file->gnode = g_node_append_data (parent_file->gnode, file);
	file->directory = directory;

	print_tree (root, 0);

	return file;
}

static gboolean
free_files_func (GNode *gnode, gpointer data)
{
	FakeNode *file = gnode->data;

	g_print ("REMOVE: %s\n", file->name);
	
	g_free (file->name);
	g_free (file->content);
	g_free (file);

	return FALSE;
}

static GnomeVFSResult
remove_fake_node_by_uri (const GnomeVFSURI *uri)
{
	FakeNode *file;
	GNode    *gnode;

	file = get_fake_node_from_uri (uri);
	if (!file) {
		return GNOME_VFS_ERROR_INVALID_URI;
	}
	
	gnode = file->gnode;
	g_node_unlink (gnode);
	
	g_node_traverse (gnode,
			 G_PRE_ORDER,
			 G_TRAVERSE_ALL,
			 -1,
			 free_files_func,
			 NULL);

	g_node_destroy (gnode);

	print_tree (root, 0);

	return GNOME_VFS_OK;
}

static GnomeVFSResult
do_open (GnomeVFSMethod        *method,
	 GnomeVFSMethodHandle **method_handle,
	 GnomeVFSURI           *uri,
	 GnomeVFSOpenMode       mode,
	 GnomeVFSContext       *context)
{
	FakeNode   *file;
	FileHandle *handle; 
	
	g_print ("do_open ('%s')\n", uri->text);

	file = get_fake_node_from_uri (uri);
	if (file && file->directory) {
		return GNOME_VFS_ERROR_IS_DIRECTORY;
	}

	/* We don't support random mode. */
	if (mode & GNOME_VFS_OPEN_RANDOM) {
		return GNOME_VFS_ERROR_INVALID_OPEN_MODE;
	}

	if (mode & GNOME_VFS_OPEN_WRITE) {
		file = get_fake_node_from_uri (uri);
		if (file) {
			g_free (file->content);
			file->content = NULL;
		} else {
			file = add_fake_node (uri, FALSE);
		}
	} else if (mode & GNOME_VFS_OPEN_READ) {
		file = get_fake_node_from_uri (uri);
		if (!file) {
			return GNOME_VFS_ERROR_NOT_FOUND;
		}
	} else {
		return GNOME_VFS_ERROR_INVALID_OPEN_MODE;
	}

	handle = g_new0 (FileHandle, 1);
	handle->fnode = file;
			
	*method_handle = (GnomeVFSMethodHandle *) handle;
		
	return GNOME_VFS_OK;
}

static GnomeVFSResult
do_create (GnomeVFSMethod        *method,
	   GnomeVFSMethodHandle **method_handle,
	   GnomeVFSURI           *uri,
	   GnomeVFSOpenMode       mode,
	   gboolean               exclusive,
	   guint                  perm,
	   GnomeVFSContext       *context)
{
	g_print ("do_create\n");

	return do_open (method, method_handle, uri, mode, context);
}

static GnomeVFSResult
do_read (GnomeVFSMethod       *method,
	 GnomeVFSMethodHandle *method_handle,
	 gpointer              buffer,
	 GnomeVFSFileSize      bytes,
	 GnomeVFSFileSize     *bytes_read,
	 GnomeVFSContext      *context)
{
	FileHandle *handle = (FileHandle *) method_handle;

	g_print ("do_read\n");

	if (!handle->str) {
		/* This is the first pass, get the content string. */
		handle->str = g_strdup (handle->fnode->content);
		handle->len = handle->fnode->size;
		handle->bytes_written = 0;
	}

	if (handle->bytes_written >= handle->len) {
		/* The whole file is read, return EOF. */
		return GNOME_VFS_ERROR_EOF;
	}
	
	*bytes_read = MIN (bytes, handle->len - handle->bytes_written);

	memcpy (buffer, handle->str + handle->bytes_written, *bytes_read);
	
	handle->bytes_written += *bytes_read;

	return GNOME_VFS_OK;
}

static GnomeVFSResult
do_write (GnomeVFSMethod       *method,
	  GnomeVFSMethodHandle *method_handle,
	  gconstpointer         buffer,
	  GnomeVFSFileSize      bytes,
	  GnomeVFSFileSize     *bytes_written,
	  GnomeVFSContext      *context)
{
	FileHandle *handle = (FileHandle *) method_handle;
	FakeNode   *file;

	g_print ("do_write\n");

	file = handle->fnode;

	file->content = g_memdup (buffer, bytes);
	file->size = bytes;

	*bytes_written = bytes;

	//g_print ("bytes_written: %d\n", (int)bytes);
	//g_print ("'%s'\n", file->content);
	
	return GNOME_VFS_OK;
}

static GnomeVFSResult
do_close (GnomeVFSMethod       *method,
	  GnomeVFSMethodHandle *method_handle,
	  GnomeVFSContext      *context)
{
	FileHandle *handle = (FileHandle *) method_handle;
	
	g_print ("do_close\n");

	g_print ("Wrote: '%s'\n", handle->str);
	
	g_free (handle->str);
	g_free (handle);

	invoke_monitors ();

	print_tree (root, 0);
	
	return GNOME_VFS_OK;
}

static GnomeVFSResult
do_open_directory (GnomeVFSMethod           *method,
		   GnomeVFSMethodHandle    **method_handle,
		   GnomeVFSURI              *uri,
		   GnomeVFSFileInfoOptions   options,
		   GnomeVFSContext          *context)
{
	const gchar *path;
	DirHandle   *handle;
	FakeNode    *file;

	g_print ("do_open_directory: '%s'\n", uri->text);

	path = gnome_vfs_uri_get_path (uri);
	if (!path) {
		path = "/";
	}

	handle = g_new0 (DirHandle, 1);
	handle->options = options;
	
	file = get_fake_node_from_uri (uri);
	if (file) {
		handle->gnode = file->gnode;
		handle->current_child = handle->gnode->children;
	} else {
		return GNOME_VFS_ERROR_NOT_FOUND;
	}

	*method_handle  = (GnomeVFSMethodHandle *) handle;

	return GNOME_VFS_OK;
}

static GnomeVFSResult
do_read_directory (GnomeVFSMethod       *method,
		   GnomeVFSMethodHandle *method_handle,
		   GnomeVFSFileInfo     *file_info,
		   GnomeVFSContext      *context)
{
	DirHandle *handle = (DirHandle *) method_handle;
	FakeNode  *file;

	g_print ("do_read_directory\n");
	
	if (!handle->current_child) {
		return GNOME_VFS_ERROR_EOF;
	}

	file = handle->current_child->data;

	if (file->directory) {
		file_info->type = GNOME_VFS_FILE_TYPE_DIRECTORY;
		file_info->valid_fields |= GNOME_VFS_FILE_INFO_FIELDS_TYPE;
		file_info->mime_type = g_strdup ("x-directory/normal");
		file_info->valid_fields |= GNOME_VFS_FILE_INFO_FIELDS_MIME_TYPE;
	} else {
		file_info->type = GNOME_VFS_FILE_TYPE_REGULAR;
		file_info->valid_fields |= GNOME_VFS_FILE_INFO_FIELDS_TYPE;
		file_info->mime_type = g_strdup ("text/plain");
		file_info->valid_fields |= GNOME_VFS_FILE_INFO_FIELDS_MIME_TYPE;
		file_info->size = file->size;
		file_info->valid_fields |= GNOME_VFS_FILE_INFO_FIELDS_SIZE;
	}		

	file_info->name = g_strdup (file->name);

	handle->current_child = handle->current_child->next;

	return GNOME_VFS_OK;
}

static GnomeVFSResult
do_close_directory (GnomeVFSMethod       *method,
		    GnomeVFSMethodHandle *method_handle,
		    GnomeVFSContext      *context)
{
	DirHandle *handle = (DirHandle *) method_handle;

	g_print ("do_close_directory\n");

	g_free (handle);

	return GNOME_VFS_OK;
}

static GnomeVFSResult
do_get_file_info (GnomeVFSMethod          *method,
		  GnomeVFSURI             *uri,
		  GnomeVFSFileInfo        *file_info,
		  GnomeVFSFileInfoOptions  options,
		  GnomeVFSContext         *context)
{
	const gchar *path;
	FakeNode    *file;

	g_print ("do_get_file_info\n");

	path = gnome_vfs_uri_get_path (uri);
	if (!path) {
		return GNOME_VFS_ERROR_INVALID_URI;
	}

	if (path[0] == '/') {
		path++;
	}

	file = get_fake_node_from_uri (uri);
	if (!file) {
		return GNOME_VFS_ERROR_NOT_FOUND;
	}

	if (file->gnode == root) {
		/* Root directory. */
		file_info->name = g_strdup ("Tutorial");
	} else {
		file_info->name = g_strdup (file->name);
	}
	
	if (file->directory) {
		file_info->type = GNOME_VFS_FILE_TYPE_DIRECTORY;
		file_info->valid_fields |= GNOME_VFS_FILE_INFO_FIELDS_TYPE;
		file_info->mime_type = g_strdup ("x-directory/normal");
		file_info->valid_fields |= GNOME_VFS_FILE_INFO_FIELDS_MIME_TYPE;
	} else {
		file_info->type = GNOME_VFS_FILE_TYPE_REGULAR;
		file_info->valid_fields |= GNOME_VFS_FILE_INFO_FIELDS_TYPE;
		file_info->mime_type = g_strdup ("text/plain");
		file_info->valid_fields |= GNOME_VFS_FILE_INFO_FIELDS_MIME_TYPE;
		file_info->size = file->size;
		file_info->valid_fields |= GNOME_VFS_FILE_INFO_FIELDS_SIZE;

		g_print ("size: %d\n", (gint) file_info->size);
	}		
	
	return GNOME_VFS_OK;
}

static gboolean
do_is_local (GnomeVFSMethod    *method,
	     const GnomeVFSURI *uri)
{
	return TRUE;
}

static GnomeVFSResult
do_make_directory (GnomeVFSMethod  *method,
		   GnomeVFSURI     *uri,
		   guint            perm,
		   GnomeVFSContext *context)
{
	GnomeVFSResult  result;
	FakeNode       *file;
	
	file = add_fake_node (uri, TRUE);

	if (file) {
		result = GNOME_VFS_OK;
	} else {
		result = GNOME_VFS_ERROR_NOT_PERMITTED;
	}

	return result;
}

static GnomeVFSResult
do_remove_directory (GnomeVFSMethod  *method,
		     GnomeVFSURI     *uri,
		     GnomeVFSContext *context)
{
	FakeNode *file;

	g_print ("do_remove_directory ('%s')\n", uri->text);
	
	file = get_fake_node_from_uri (uri);
	
	if (!file) {
		return GNOME_VFS_ERROR_INVALID_URI;
	}

	/* Can't remove the root. */
	if (file->gnode == root) {
		return GNOME_VFS_ERROR_NOT_PERMITTED;
	}

	/* Can't remove non-empty directories. */
	if (g_node_n_children (file->gnode) > 0) {
		return GNOME_VFS_ERROR_NOT_PERMITTED;
	}

	return remove_fake_node_by_uri (uri);
}

static GnomeVFSResult
do_unlink (GnomeVFSMethod  *method,
	   GnomeVFSURI     *uri,
	   GnomeVFSContext *context)
{
	FakeNode *file;

	g_print ("do_unlink ('%s')\n", uri->text);
	
	file = get_fake_node_from_uri (uri);
	
	if (!file) {
		return GNOME_VFS_ERROR_INVALID_URI;
	}

	/* Can't remove the root. */
	if (file->gnode == root) {
		return GNOME_VFS_ERROR_NOT_PERMITTED;
	}

	/* Can't remove directories. */
	if (file->directory) {
		return GNOME_VFS_ERROR_NOT_PERMITTED;
	}

	invoke_monitors ();

	return remove_fake_node_by_uri (uri);
}

static GnomeVFSResult
do_monitor_add (GnomeVFSMethod        *method,
		GnomeVFSMethodHandle **method_handle,
		GnomeVFSURI           *uri,
		GnomeVFSMonitorType    monitor_type)
{
	FakeNode    *file;
	GnomeVFSURI *uri_copy;

	file = get_fake_node_from_uri (uri);
	if (!file) {
		return GNOME_VFS_ERROR_INVALID_URI;
	}
	
	if (!file->directory || monitor_type != GNOME_VFS_MONITOR_DIRECTORY) {
		return GNOME_VFS_ERROR_NOT_SUPPORTED;
	}
	
	uri_copy = gnome_vfs_uri_dup (uri);

	*method_handle = (GnomeVFSMethodHandle *) uri_copy;

	//G_LOCK (monitor_list);
	monitor_list = g_list_prepend (monitor_list, uri_copy);
	//G_UNLOCK (monitor_list);

	return GNOME_VFS_OK;
}

static GnomeVFSResult
do_monitor_cancel (GnomeVFSMethod       *method,
		   GnomeVFSMethodHandle *method_handle)
{
	GnomeVFSURI *uri;
	
	uri = (GnomeVFSURI *) method_handle;

	//G_LOCK (monitor_list);
	monitor_list = g_list_remove (monitor_list, uri);
	//G_UNLOCK (monitor_list);

	gnome_vfs_uri_unref (uri);

	return GNOME_VFS_OK;
}

static GnomeVFSMethod method = {
	sizeof (GnomeVFSMethod),

        do_open,                /* open */
        do_create,              /* create */
        do_close,               /* close */
        do_read,                /* read */
        do_write,               /* write */
        NULL,                   /* seek */
        NULL,                   /* tell */
        NULL,                   /* truncate_handle */ 
        do_open_directory,
	do_close_directory,
        do_read_directory,
        do_get_file_info,
        NULL,                   /* get_file_info_from_handle */
        do_is_local,            /* is_local */
        do_make_directory,      /* make_directory */
        do_remove_directory,    /* remove_directory */
        NULL,                   /* move */
        do_unlink,              /* unlink */
        NULL,                   /* check_same_fs */
        NULL,                   /* set_file_info */
        NULL,                   /* truncate */
        NULL,                   /* find_directory */
        NULL,                   /* create_symbolic_link */
	do_monitor_add,         /* monitor_add */
	do_monitor_cancel,      /* monitor_cancel */
	NULL                    /* file_control */
};

GnomeVFSMethod *
vfs_module_init (const char *method_name, const char *args)
{
	if (strcmp (method_name, "tutorial") == 0) {
		init_fake_tree ();

		g_print ("---------------------------\n");
		
		return &method;
	}
	
	return NULL;
}
 
void
vfs_module_shutdown (GnomeVFSMethod* method)
{
	free_fake_tree ();
}


