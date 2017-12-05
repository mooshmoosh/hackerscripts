#include <stdlib.h>
#include <stdio.h>
#include <ctype.h>
#include <assert.h>
#include <string.h>

struct _LispPair;
struct _LispPair {
    void * data;
    struct _LispPair * next;
};
typedef struct _LispPair * LispPair;

struct _LispParser {
    LispPair root;
    LispPair parent;
    LispPair strings;
    LispPair * next_list;
    enum {
        LISP_PARSER_BETWEEN_ATOMS,
        LISP_PARSER_IN_SYMBOL
    } current_state;
    char * buffer;
    unsigned int buffer_size;
    unsigned int symbol_length;
    unsigned int line_number;
    unsigned int character_number;
    unsigned int error;
    const char * error_message;
};
typedef struct _LispParser * LispParser;

LispPair lisppair_new(void * data, LispPair next)
{
    LispPair result = calloc(1, sizeof(struct _LispPair));
    assert((unsigned long long int) result % 2 == 0);
    result->data = data;
    result->next = next;
    return result;
}

LispParser lispparser_new()
{
    LispParser result = calloc(1, sizeof(struct _LispParser));
    result->root = NULL;
    result->next_list = &result->root;
    result->parent = NULL;
    result->strings = NULL;
    result->current_state = LISP_PARSER_BETWEEN_ATOMS;
    result->buffer_size = 64;
    result->buffer = calloc(result->buffer_size, 1);
    result->symbol_length = 0;
    result->line_number = 0;
    result->character_number = 0;
    return result;
}

void * lispparser_create_object(LispParser parser, const char * symbol, unsigned int symbol_length)
{
    LispPair string;
    for (string = parser->strings; string != NULL; string = string->next) {
        if (!strncmp((const char *) string->data, symbol, symbol_length)) {
            return (void*) ((unsigned long long int)string->data | 1);
        }
    }
    char * result = calloc(symbol_length + 1, 1);
    assert((unsigned long long int) result % 2 == 0);
    strncpy(result, symbol, symbol_length);
    result[symbol_length] = '\0';
    parser->strings = lisppair_new(result, parser->strings);
    return (void *) ((unsigned long long int) result | 1);
}

void lispparser_append_item(LispParser parser, void * item)
{
    (*(parser->next_list)) = lisppair_new(item, NULL);
    parser->next_list = &(parser->next_list->next);
}

void lispparser_add_new_list(LispParser parser)
{
    LispPair old_next_list = parser->next_list;
    lispparser_append_item(parser, lisppair_new(NULL, NULL))
    parser->parent = lisppair_new(parser->next_list, parser->parent);
}

void lispparser_current_list_ends(LispParser parser)
{
    if (parser->parent == NULL) {
        parser->error = 1;
        return;
    }
    LispPair old_parent = parser->parent;
    parser->parent = parser->parent->next;
    parser->next_item = &(parser->parent->data);
    free(old_parent);
}

void lispparser_handle_space(LispParser parser)
{
    if (parser->current_state == LISP_PARSER_IN_SYMBOL) {
        parser->current_state = LISP_PARSER_BETWEEN_ATOMS;
        parser->buffer[parser->symbol_length] = '\0';
        *(parser->next_item) = lispparser_create_object(parser, parser->buffer, parser->symbol_length);
        parser->next_item = &(parser->parent->data);
        parser->symbol_length = 0;
    }
}

void lispparser_handle_handle_char(LispParser parser, unsigned char character)
{
    if (parser->current_state == LISP_PARSER_BETWEEN_ATOMS) {
        parser->current_state = LISP_PARSER_IN_SYMBOL;
    }

    parser->buffer[parser->symbol_length++] = character;
    if (parser->symbol_length >= parser->buffer_size) {
        parser->buffer_size += 64;
        parser->buffer = realloc(parser->buffer, parser->buffer_size);
    }
}

void lispparser_take_char(LispParser parser, int character)
{
    if (character == '\n') {
        parser->line_number++;
        parser->character_number = 0;
    } else {
        parser->character_number++;
    }

    if (character == '(') {
        lispparser_add_new_list(parser);
    } else if (character == ')') {
        lispparser_current_list_ends(parser);
    } else if (isspace(character)) {
        lispparser_handle_space(parser);
    } else {
        lispparser_handle_handle_char(parser, (unsigned char) character);
    }
}

LispPair lispparser_get_result(LispParser parser)
{
    return parser->root;
}

void lispparser_delete(LispParser parser)
{

}

void * lisppair_get_data(LispPair pair)
{
    return (void*) (((unsigned long long int)pair->data >> 1) << 1);
}

int lisppair_data_is_pair(LispPair obj)
{
    return !((unsigned long long int) obj->data & 1);
}

void lisppair_print(LispPair obj);

void lisppair_print_remaining(LispPair obj)
{
    if (obj == NULL) {
        printf(")");
        return;
    } else {
        printf(" ");
    }

    if (lisppair_data_is_pair(obj)) {
        lisppair_print(lisppair_get_data(obj));
    } else {
        printf("%s", lisppair_get_data(obj));
    }
    lisppair_print_remaining(obj->next);
}

void lisppair_print(LispPair obj)
{
    printf("(");
    if (lisppair_data_is_pair(obj)) {
        lisppair_print(obj->data);
    } else {
        printf("%s", lisppair_get_data(obj));
    }
    lisppair_print_remaining(obj->next);
}

int main()
{
    FILE * fhandle = fopen("test_lisp.txt", "r");
    LispParser parser = lispparser_new();
    while (!feof(fhandle)) {
        lispparser_take_char(parser, fgetc(fhandle));
    }
    fclose(fhandle);
    LispPair result = lispparser_get_result(parser);
    lisppair_print(result);
    lispparser_delete(parser);
}

