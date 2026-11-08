/* SPDX-License-Identifier: GPL-3.0-or-later
 * Madeira Converter Exception: see LICENSE-EXCEPTION.md (this file only). */
#include <assert.h>
#include <stdio.h>
#include "../../build/ntdll-unix/ios_cef_fatal_site.h"

static unsigned char object[512], code[3] = {0xcc,0x0f,0x0b};
static char path[256];
static int deny;
static int read_memory(uint64_t address, void *out, size_t size, void *opaque)
{
    struct { uint64_t address; void *data; size_t length; } regions[] = {
        {0x1000, code, sizeof(code)}, {0x2000, object, sizeof(object)}, {0x4000, path, sizeof(path)}
    };
    (void)opaque;
    if (deny) return 0;
    for (size_t i=0; i<sizeof(regions)/sizeof(regions[0]); i++)
        if (address >= regions[i].address && address-regions[i].address <= regions[i].length &&
            size <= regions[i].length-(address-regions[i].address))
        {
            memcpy(out, (char *)regions[i].data+address-regions[i].address, size);
            return 1;
        }
    return 0;
}
static void setup(void)
{
    uint64_t file=0x4000; uint32_t severity=3, line=180;
    memset(object,0,sizeof(object)); memset(path,0,sizeof(path));
    memcpy(object+8,&severity,4); memcpy(object+0x120,&file,8); memcpy(object+0x128,&line,4);
    strcpy(path,"..\\partition_alloc\\page_allocator_internals_win.h");
}
int main(void)
{
    struct ios_cef_fatal_site site;
    setup(); assert(ios_cef_fatal_site_read(0x1001,0x2000,read_memory,NULL,&site));
    assert(site.line==180 && site.severity==3 && !strcmp(site.file,"page_allocator_internals_win.h"));
    strcpy(path,"/src/partition_alloc/page_allocator.cc");
    assert(ios_cef_fatal_site_read(0x1001,0x2000,read_memory,NULL,&site));
    assert(!strcmp(site.file,"page_allocator.cc"));
    strcpy(path,"private-unrelated-file.cc");
    assert(!ios_cef_fatal_site_read(0x1001,0x2000,read_memory,NULL,&site)); assert(!site.file);
    setup(); deny=1; assert(!ios_cef_fatal_site_read(0x1001,0x2000,read_memory,NULL,&site)); deny=0;
    code[0]=0x90; assert(!ios_cef_fatal_site_read(0x1001,0x2000,read_memory,NULL,&site)); code[0]=0xcc;
    object[8]=2; assert(!ios_cef_fatal_site_read(0x1001,0x2000,read_memory,NULL,&site));
    setup(); memset(path,'x',sizeof(path)); assert(!ios_cef_fatal_site_read(0x1001,0x2000,read_memory,NULL,&site));
    setup(); path[0]=1; assert(!ios_cef_fatal_site_read(0x1001,0x2000,read_memory,NULL,&site));
    assert(!ios_cef_fatal_site_read(UINT64_MAX,0x2000,read_memory,NULL,&site));
    assert(!ios_cef_fatal_site_read(0x1001,UINT64_MAX,read_memory,NULL,&site));
    setup(); memset(object+0x120,0xff,8);
    assert(!ios_cef_fatal_site_read(0x1001,0x2000,read_memory,NULL,&site));
    puts("PASS: actual fatal-site reader, inaccessible/overflow input, trap/severity/path validation");
}
