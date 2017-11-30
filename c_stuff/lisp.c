#include <stdlib.h>
#include <stdio.h>
#include <ctype.h>

struct _LispPair;
struct _LispPair;
{
    void * data;
    struct _LispPair * next;
};
typedef _LispPair * LispPair;

struct _LispParser {
    void * root;
    LispPair parent;
    LispPair strings;
    void ** next_item;
    LispPair current_list;
    enum {
        LISP_PARSER_BETWEEN_ATOMS,
        LISP_PARSER_IN_SYMBOL
    } current_state;
    char * buffer;
    unsigned int buffer_size;
    unsigned int symbol_length
};
typedef struct _LispParser * LispParser;

LispParser lispparser_new()
{
    LispParser result = calloc(1, sizeof(struct _LispParser));
    result->parent = NULL;
    result->root = NULL
    result->strings = NULL;
    result->next_item = &(result->root);
    result->current_state = LISP_PARSER_BETWEEN_ATOMS;
    result->buffer_size = 64;
    result->buffer = calloc(result->buffer_size, 1);
    result->symbol_length = 0;
    return result;
}

LispPair lisppair_new(void * data, LispPair next)
{
    LispPair result = calloc(1, sizeof(struct _LispPair));
    result->data = data;
    result->next = next;
    return result;
}

void lispparser_add_new_list(LispParser parser)
{
    *(parser->next_item) = lisppair_new(NULL, NULL);
    parser->parent = lisppair_new(*(parser->next_item), parser->parent);
    parser->next_item = &(parser->parent->data);
}

void lispparser_current_list_ends(LispParser parser)
{
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
        *(parser->next_item) = lispparser_create_object(parser->buffer);
        parser->next_item = &(parser->parent->data);
    }
}

void lispparser_handle_handle_char(LispParser parser, unsigned char character)
{
    if (parser->current_state == LISP_PARSER_BETWEEN_ATOMS) {
        parser->current_state = LISP_PARSER_IN_SYMBOL;
        parser->buffer[parser->symbol_length++] = character;
    }
}

void lispparser_take_char(LispParser parser, int character)
{
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

void lisppair_print(LispPair obj)
{

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
