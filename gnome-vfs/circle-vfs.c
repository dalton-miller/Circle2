/* -*- Mode: C; tab-width: 8; indent-tabs-mode: t; c-basic-offset: 8 -*- */
/*
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
#include <sys/types.h>
#include <sys/socket.h>
#include <sys/un.h>
#include <stdio.h>
#include <libgnomevfs/gnome-vfs.h>
#include <libgnomevfs/gnome-vfs-module.h>

/* A fake node (file or directory) in our fake file system. */
typedef struct {
	GNode    *gnode;
	gchar    *name;
	gboolean  directory;

	/* Only valid for files. */
	//gchar    *content;
	gint      size;
	gchar    *mime_type;
} FakeNode;

typedef struct {
	FakeNode *fnode;

	gchar    *str;
	gint      size;
	gint      bytes_written;
} FileHandle;

typedef struct {
	GnomeVFSFileInfoOptions  options;

	GNode                   *gnode;
	GNode                   *current_child;
} DirHandle; 

G_LOCK_DEFINE_STATIC (root);
static GNode *root = NULL;

char current_key[255];



static FakeNode *
new_node (char *buffer)
{
	FakeNode *file;

	gchar **strv, **p;
	gint  file_size;
	gchar *file_name;
	gchar *file_type;
	gint  l;

	//parse the line, split it using spaces
	file_name = NULL;
	file_size = 0;
	file_type = NULL;

	g_message("new node, %s",buffer);

	/*at some point I will need a real parser
	//parse (key, value) pairs
	i=0;
	while(1){
		for(;buffer[i]!="'";i++){}
		j=i+1;
		for(;buffer[j]!="'";j++){}
		buffer[j]=0;
		key=strdup(buffer[i]);
		i=j+1;
		for(;buffer[i]!="'";i++){}
		j=i+1;
		for(;buffer[j]!="'";j++){}
		buffer[j]=0;
		}*/


	strv = g_strsplit (buffer, " ", 0);
	p = strv;
	while (*p) {
		if(!g_strcasecmp("'filename':",*p)){
			p++;
			l=strlen(*p);
			(*p)[0]=' ';
			(*p)[l-1]=' ';
			(*p)[l-2]=' ';
			file_name = g_strdup (*p);
			g_strstrip(file_name);
		}
		if(!g_strcasecmp("'length':",*p)){
			p++;
			sscanf(*p,"%dL",&file_size);
			//g_message(*p);
		}
		if(!g_strcasecmp("'mime':",*p)){
			p++;
			l=strlen(*p);
			(*p)[0]=' ';
			(*p)[l-1]=' ';
			(*p)[l-2]=' ';
			file_type = g_strdup (*p);
			g_strstrip(file_type);
		}
		p++;
	}
	g_strfreev (strv);

	if(file_name!=NULL){
		file = g_new0 (FakeNode, 1);
		file->name = g_strdup (file_name);
		if(file_size!=0) file->size = file_size;
		//note: nautilus crashes if mime_type remain NULL 
		if(file_type!=NULL) 
			file->mime_type = g_strdup(file_type);
		else 
			file->mime_type = g_strdup("");
		file->directory = FALSE;
		return file;
	} else return NULL;
	

}


static gboolean
free_files_func (GNode *gnode, gpointer data)
{
	FakeNode *file = gnode->data;

	g_free (file->name);
	//g_free (file->content);
	g_free (file);

	return FALSE;
}



void error(char *msg)
{
    perror(msg);
    //exit(0);
}


static void init_fake_tree (char* request)
// we init the tree on every new request
{
	FakeNode *file;

	int sockfd, servlen, n, l;
	struct sockaddr_un  serv_addr;
	char buffer[2000]; //fix possible overflow
	char z;

	/* Create a fake directory structure. */
	file = g_new0 (FakeNode, 1);
	file->name = g_strdup ("<root>");
	root = g_node_new (file);
	file->gnode = root;
	file->directory = TRUE;

	//connect to socket... gotta do it every time?

	bzero((char *)&serv_addr,sizeof(serv_addr));
	serv_addr.sun_family = AF_UNIX;
	strcpy(serv_addr.sun_path, "/home/voegtlin/.circle/daemon_socket");
	servlen = strlen(serv_addr.sun_path) + 
		sizeof(serv_addr.sun_family);
	if ((sockfd = socket(AF_UNIX, SOCK_STREAM,0)) < 0)
		error("Creating socket");
	if (connect(sockfd, (struct sockaddr *) &serv_addr, servlen) < 0)
		error("Connecting");

	write(sockfd,request,strlen(request));
	//return

	n=1;
	l=0;
	while(n>0){
		n=read(sockfd,&z,1);
		if(z=='\n'){
			buffer[l]=0;
			file = new_node (buffer);
			if(file!=NULL) file->gnode = g_node_append_data (root, file);
			l=0;
		}else {
			buffer[l]=z;
			l++;
		}
	}

}




static void
free_fake_tree (void)
{
	g_node_traverse (root,
			 G_PRE_ORDER,
			 G_TRAVERSE_ALL,
			 -1,
			 free_files_func,
			 NULL);

	g_node_destroy (root);
	root = NULL;
}



/*syntax for URIs: 
   
    circle:search:key           for list of search results
    circle:search:key/filename  for a file found above
or: circle:file:name            for any circle file
    circle:dir:address/path     for somebody's file

 */


static FakeNode *
get_fake_node_from_uri (const GnomeVFSURI *uri)

{
	//first parse the uri;
	//if search: do the search
	//if file: 

	GNode       *gnode;
	const gchar *tmp;
	gchar       *path;
	gchar prefix[1000];

	FakeNode    *file;

	//char prefix[7];
	char dest[255];
	int l;

	tmp = gnome_vfs_uri_get_path (uri);
	g_message("get_fake_node_from_uri %s",tmp);
	strcpy(prefix,tmp); 
	prefix[7]=0;
	if(strcmp(prefix,"search:")==0){

		//rechercher '/'
		for(l=7;(l<strlen(tmp)) && (tmp[l]!='/');l++);
		if(l==strlen(tmp)){
			//pas de /
			if(root!=NULL){
				if(!strcmp(current_key,tmp+7))
					return root->data;
				free_fake_tree();
			}
			strcpy(current_key,tmp+7);
			//here I should compare with the key of the current tree
			strcpy(dest,"retrieve ");
			strcat(dest,current_key);
			strcat(dest,":4\n");
			init_fake_tree(dest);
			return root->data;
		}else{
			//fichier
			//verifier qu'on a bien fait la recheche
			//if(strcmp())
			gnode = root->children;
			while (gnode) {
				file = gnode->data;
				path = file->name;
				if (strcmp (tmp+l+1,path) == 0) 
					return gnode->data;
				gnode = gnode->next;
			}
			return NULL;
		}
		
	}
	prefix[4]=0;
	if(strcmp(prefix,"dir:")==0){
		g_message("dir %s",tmp+4);
		sprintf(dest,"dir (None,[])\n");
		if(root!=NULL) free_fake_tree();
		init_fake_tree(dest);
		return root->data;
	}
	else return NULL;

}





/* Implementation of GnomeVFS module functions. */

static GnomeVFSResult
do_open (GnomeVFSMethod        *method,
	 GnomeVFSMethodHandle **method_handle,
	 GnomeVFSURI           *uri,
	 GnomeVFSOpenMode       mode,
	 GnomeVFSContext       *context)
{
	FakeNode   *file;
	FileHandle *handle; 
	
	g_message("do open");
	return GNOME_VFS_OK;


	file = get_fake_node_from_uri (uri);
	if (file && file->directory) {
		return GNOME_VFS_ERROR_IS_DIRECTORY;
	}

	/* We don't support random mode. */
	if (mode & GNOME_VFS_OPEN_RANDOM) {
		return GNOME_VFS_ERROR_INVALID_OPEN_MODE;
	}
	if (mode & GNOME_VFS_OPEN_WRITE) {
		return GNOME_VFS_ERROR_INVALID_OPEN_MODE;
	} 
	if (mode & GNOME_VFS_OPEN_READ) {
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
do_read (GnomeVFSMethod       *method,
	 GnomeVFSMethodHandle *method_handle,
	 gpointer              buffer,
	 GnomeVFSFileSize      bytes,
	 GnomeVFSFileSize     *bytes_read,
	 GnomeVFSContext      *context)
{
	FileHandle *handle = (FileHandle *) method_handle;

	g_message("do read");
	if (!handle->str) {
		/* This is the first pass, get the content string. */
		//handle->str = g_memdup (handle->fnode->content, handle->fnode->size);
		//handle->size = handle->fnode->size;
		handle->str = strdup("blah");
		handle->size = 4;
		handle->bytes_written = 0;
	}

	if (handle->bytes_written >= handle->size) {
		/* The whole file is read, return EOF. */
		*bytes_read = 0;
		return GNOME_VFS_ERROR_EOF;
	}
	
	*bytes_read = MIN (bytes, handle->size - handle->bytes_written);

	memcpy (buffer, handle->str + handle->bytes_written, *bytes_read);
	
	handle->bytes_written += *bytes_read;

	return GNOME_VFS_OK;
}


static GnomeVFSResult
do_close (GnomeVFSMethod       *method,
	  GnomeVFSMethodHandle *method_handle,
	  GnomeVFSContext      *context)
{
	FileHandle *handle = (FileHandle *) method_handle;

	g_free (handle->str);
	g_free (handle);

	return GNOME_VFS_OK;
}

static GnomeVFSResult
do_open_directory (GnomeVFSMethod           *method,
		   GnomeVFSMethodHandle    **method_handle,
		   GnomeVFSURI              *uri,
		   GnomeVFSFileInfoOptions   options,
		   GnomeVFSContext          *context)
{
	DirHandle *handle;
	FakeNode  *file;
	g_message("do open directory");

	handle = g_new0 (DirHandle, 1);
	
	file = get_fake_node_from_uri (uri);
	if (file) {
		handle->gnode = file->gnode;
		handle->current_child = handle->gnode->children;
	} else {
		return GNOME_VFS_ERROR_NOT_FOUND;
	}

	*method_handle = (GnomeVFSMethodHandle *) handle;

	g_message("do open directory returning");
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
		file_info->mime_type = g_strdup (file->mime_type);
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

	g_free (handle);

	return GNOME_VFS_OK;
}

static GnomeVFSResult
do_get_file_info (GnomeVFSMethod          *method,
		  GnomeVFSURI             *uri,
		  GnomeVFSFileInfo        *file_info,
		  GnomeVFSFileInfoOptions  options,
		  GnomeVFSContext         *context)
//here it learns whether the uri is a directory...
{
	FakeNode *file;

	g_message("do get file info");

	file = get_fake_node_from_uri (uri);
	if (!file) {
		g_message("error not found");
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
		file_info->mime_type = g_strdup (file->mime_type);
		file_info->valid_fields |= GNOME_VFS_FILE_INFO_FIELDS_MIME_TYPE;
		file_info->size = file->size;
		file_info->valid_fields |= GNOME_VFS_FILE_INFO_FIELDS_SIZE;

		//file_info->flags |= GNOME_VFS_FILE_FLAGS_SYMLINK;
		//file_info->symlink_name = g_strdup ("tutorial:file");

	}		
	
	g_message("vfs ok");
	return GNOME_VFS_OK;
}

static gboolean
do_is_local (GnomeVFSMethod    *method,
	     const GnomeVFSURI *uri)
{
	return FALSE;
	//return TRUE;
}




static GnomeVFSMethod method = {
	sizeof (GnomeVFSMethod),
	
        do_open,                /* open */
        NULL,                   /* create */
        do_close,               /* close */
        do_read,                /* read */
        NULL,                   /* write*/
        NULL,                   /* seek */
        NULL,                   /* tell */
        NULL,                   /* truncate_handle */ 
        do_open_directory,      /* do_open_directory */
	do_close_directory,     /* do_close_directory */
        do_read_directory,      /* do_read_directory */     
        do_get_file_info,       /* do_get_file_info */
        NULL,                   /* get_file_info_from_handle */
        do_is_local,            /* is_local */
        NULL,                   /* make_directory */
        NULL,                   /* remove_directory */
        NULL,                   /* move */
        NULL     ,              /* unlink */
        NULL,                   /* check_same_fs */
        NULL,                   /* set_file_info */
        NULL,                   /* truncate */
        NULL,                   /* find_directory */
        NULL,                   /* create_symbolic_link */
	NULL,                   /* monitor_add */
	NULL,                   /* monitor_cancel */
	NULL                    /* file_control */
};

GnomeVFSMethod *
vfs_module_init (const char *method_name, const char *args)
{
	if (strcmp (method_name, "circle") == 0) {

		return &method;
	}


	
	return NULL;
}
 
void
vfs_module_shutdown (GnomeVFSMethod* method)
{
	free_fake_tree ();
}

 
