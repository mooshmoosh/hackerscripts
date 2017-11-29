#include <stdio.h>
#include <stdlib.h>
#include <ctype.h>

typedef struct
{
    char * buffer;
    unsigned int buffer_size;
    char ** pointers;
    unsigned int pointer_count;
    FILE * file_handle;
} SSVLineIterator;

typedef struct
{
    char ** values;
    unsigned int length;
} SSVRow;

SSVLineIterator ssv_read_file(const char * filename)
{
    SSVLineIterator result;
    result.buffer_size = 256;
    result.buffer = malloc(sizeof(char) * result.buffer_size);
    result.pointer_count = 5;
    result.pointers = malloc(sizeof(char*) * result.pointer_count);
    result.file_handle = fopen(filename, "r");
    return result;
}

SSVRow ssv_next(SSVLineIterator * itt)
{
    SSVRow result;
    result.length = 0;
    unsigned int next_char = 0;
    int c = fgetc(itt->file_handle);
    char * old_buffer;
    int i;
    if (feof(itt->file_handle)) {
        return result;
    }
    while (isspace(c))
    {
        c = fgetc(itt->file_handle);
    }
    itt->pointers[result.length++] = itt->buffer;
    while (!feof(itt->file_handle) && c != '\n' && c != '\r') {
        if (result.length >= itt->pointer_count) {
            itt->pointer_count += 5;
            itt->pointers = realloc(itt->pointers, sizeof(char*) * itt->pointer_count);
        }
        if (next_char > itt->buffer_size) {
            old_buffer = itt->buffer;
            itt->buffer_size += 256;
            itt->buffer = realloc(itt->buffer, sizeof(char) * itt->buffer_size);
            for (i = 0; i < result.length; i++) {
                itt->pointers[i] = (itt->pointers[i] - old_buffer + itt->buffer);
            }
        }
        if (isspace(c)) {
            itt->buffer[next_char++] = '\0';
            itt->pointers[result.length++] = &(itt->buffer[next_char]);
            while (isspace(c)) {
                c = fgetc(itt->file_handle);
            }
        } else {
            itt->buffer[next_char++] = c;
            itt->buffer[next_char] = '\0';
            c = fgetc(itt->file_handle);
        }
    }
    itt->buffer[next_char] = '\0';
    result.values = itt->pointers;
    return result;
}

void ssv_close_file(SSVLineIterator * itt)
{
    fclose(itt->file_handle);
    free(itt->buffer);
    free(itt->pointers);
}

int main() {
    SSVLineIterator itt = ssv_read_file("ssv_test_file.txt");
    SSVRow row;
    row = ssv_next(&itt);
    while (row.length != 0) {
        printf("row.length = %d\n", row.length);
        printf("row.values = (");
        unsigned int i;
        for (i = 0; i < row.length; i++) {
            printf("'%s'", row.values[i]);
            if (i < row.length - 1) {
                printf(", ");
            }
        }
        printf(")\n");
        row = ssv_next(&itt);
    }
    ssv_close_file(&itt);
}
