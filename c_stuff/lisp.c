#include <stdio.h>
#include <stdlib.h>
#include <ctype.h>

typedef enum {
    LISPPAIR_STRING,
    LISPPAIR_QUOTED_SYMBOL,
    LISPPAIR_SYMBOL,
    LISPPAIR_QUOTED_LIST,
    LISPPAIR_LIST,
    LISPPAIR_INT,
    LISPPAIR_DOUBLE
} LispPairType;

struct _DepthFirstLispPair
{
    // This is the depth first search orderd version of the parsed tree.
    // This is the order in which the symbols actually apear in the text
    // being parsed. In an array of these structures, the integer next refers
    // the the index of the next element in the list. The first element of
    // a list is the element that comes after the list object.
    LispPairType type;
    unsigned int next;
    union {
        unsigned int as_str_offset;
        long long int as_int;
        double as_double;
    } value;
};
typedef struct _DepthFirstLispPair * DepthFirstLispPair;

struct _LispPair
{
    // This is the breadth first search ordered version of the parsed tree.
    // This is what we return. In an array of these structures, the next
    // one is the next element of a list. Lists are represented as pointers
    // to the first element.
    LispPairType type;
    unsigned int length;
    union {
        const char * as_str;
        const char * as_symbol;
        struct LispPair * as_list;
        long long int as_int;
        double as_double;
    } value;
};
typedef struct _LispPair * LispPair;

struct _LispParser
{
    char * strings;
    unsigned int strings_capacity;
    unsigned int next_character;
    DepthFirstLispPair parsed_tree;
    LispPair result;
    unsigned int parsed_tree_size;
    int in_string;
    int escaping;
    int error;
    unsigned int line_number;
    unsigned int column_number;
};
typedef struct _LispParser * LispParser;

LispParser lispparser_new()
{
    LispParser parser = calloc(sizeof(struct _LispParser), 1);
    parser->parsed_tree_capacity = 10;
    parser->parsed_tree = calloc(sizeof(struct _DepthFirstLispPair), parser->parsed_tree_capacity);
    parser->parsed_tree_size = 0;
    parser->result = NULL;
    parser->in_string = 0;
    parser->escaping = 0;
    parser->error = 0;
    parser->line_number = 0;
    parser->column_number = 0;
    parser->strings_capacity = 256;
    parser->strings = calloc(sizeof(char), parser->strings_capacity);
    parser->next_character = 0;
    return parser;
}

void lispparser_start_escaping(LispParser parser)
{
    parser->escaping = 1;
}

void lispparser_close_string(LispParser parser)
{

}

void lispparser_add_to_string(LispParser parser, unsigned char character)
{

}

void lispparser_add_escaped_character(LispParser parser, unsigned char character)
{
    if (character == 'n') {
        lispparser_add_to_string(parser, '\n');
    } else if (character == '\\') {
        lispparser_add_to_string(parser, '\\');
    } else if (character == 't') {
        lispparser_add_to_string(parser, '\t');
    } else if (character == '"') {
        lispparser_add_to_string(parser, '"');
    } else {
        lispparser_add_to_string(parser, character);
    }
    parser->escaping = 0;
}

void lispparser_begin_string(LispParser parser)
{

}

void lispparser_begin_list(LispParser parser)
{

}

void lispparser_end_list(LispParser parser)
{

}

void lispparser_handle_space(LispParser parser)
{

}

void lispparser_handle_atom_char(LispParser parser, unsigned char character)
{

}

void lispparser_take_char(LispParser parser, unsigned char character)
{
    // For every character we process we keep tract of the line number and
    // column we're up to.If we encounter a syntax error, the parser knows
    // where it was.
    if (character == '\n') {
        parser->line_number++;
        parser->column_number = 0;
    } else if (character == '\r') {

    } else {
        parser.column_number++;
    }

    if (parser->in_string) {
        if (parser->escaping) {
            lispparser_add_escaped_character(parser, character);
        } else {
            if (character == '\\') {
                lispparser_start_escaping(parser);
            } else if (character == '"') {
                lispparser_close_string(parser);
            } else {
                lispparser_add_to_string(parser, character);
            }
        }
    } else {
        if (parser->escaping) {
            lispparser->error = 1;
            lispparser->error_msg = "The parser is escaping outside a string literal";
            return;
        } else if (character == '"') {
            lispparser_begin_string(parser);
        } else if (character == '(') {
            lispparser_begin_list(parser);
        } else if (character == ')') {
            lispparser_end_list(parser);
        } else if (isspace(character)) {
            lispparser_handle_space(parser);
        } else {
            lispparser_handle_atom_char(parser, character);
        }
    }
}

void lisppair_print(LispPair pair)
{

}

LispPair lispparser_get_root(LispParser parser)
{
    if (parser->result != NULL) {
        return parser->result;
    }

    parser->result = calloc(sizeof(struct _LispPair), parser->parsed_tree_size);
    unsigned int i = 0;
    unsigned int next_element = 0;
    while (i < parser->parsed_tree_size)
    {
        if (parser->parsed_tree[i].type == LISPPAIR_LIST) {
            // the length of lists is stored in the value.as_int field
            parser->result[next_element].type = LISPPAIR_LIST;
            parser->result[next_element].length = parser->parsed_tree[i].value.as_int;
            // We set the pointer to the first element of the list to null untill we load it.
            parser->result[next_element].value.as_list = NULL;
        } else {
        }
        i = parser->parsed_tree[i].next;
    }
    return parser->result;
}

void lispparser_delete(LispParser parser)
{

}

int main()
{
    FILE * handle = fopen("test_lisp.txt", "r");
    LispParser parser = lispparser_new();
    while (!feof(handle) && !parser->error) {
        lispparser_take_char(parser, fgetc(handle));
    }
    if (parser->error) {
        printf("There was a parser error: %s\n", parser->error_msg);
        return 1;
    }
    lisppair_print(lispparser_get_root(parser));
    lispparser_delete(parser);
}
