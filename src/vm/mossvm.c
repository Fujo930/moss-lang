/* Moss VM — portable C implementation of the Moss bytecode virtual machine.
 *
 * Build:  cc -o mossvm mossvm.c -lm
 * Usage:  mossvm program.mbc
 *
 * Reads the .mbc binary format, deserializes the bytecode module, and
 * executes it on a stack-based VM.  All 32 opcodes from the Moss
 * instruction set are supported.
 *
 * v0.17.0 — Reasonix, 2026
 */

#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <stdbool.h>

/* ── Value types ──────────────────────────────────────────────────── */

typedef enum { V_NULL, V_NUMBER, V_BOOL, V_STRING, V_LIST, V_RECORD, V_VARIANT, V_RESULT, V_CODE } ValueKind;

typedef struct Value {
    ValueKind kind;
    union {
        double   number;
        bool     boolean;
        char    *string;
        struct {
            struct Value **items;
            int32_t count;
        } list;
        struct {
            char       **keys;
            struct Value **vals;
            int32_t count;
        } record;
        struct {
            char *name;
            struct Value *payload;
        } variant;
        struct {
            bool ok;
            struct Value *value;
        } result;
        struct {
            uint8_t  *instructions;
            int32_t  *args;
            int32_t   length;
            int32_t   local_count;
            char    **local_names;
        } code;
    } as;
} Value;

static Value *val_null(void) {
    Value *v = calloc(1, sizeof(Value));
    v->kind = V_NULL;
    return v;
}

static Value *val_number(double n) {
    Value *v = calloc(1, sizeof(Value));
    v->kind = V_NUMBER;
    v->as.number = n;
    return v;
}

static Value *val_bool(bool b) {
    Value *v = calloc(1, sizeof(Value));
    v->kind = V_BOOL;
    v->as.boolean = b;
    return v;
}

static Value *val_string(const char *s) {
    Value *v = calloc(1, sizeof(Value));
    v->kind = V_STRING;
    v->as.string = strdup(s ? s : "");
    return v;
}

static void val_print(FILE *fp, Value *v) {
    if (!v) { fprintf(fp, "null"); return; }
    switch (v->kind) {
    case V_NULL:    fprintf(fp, "null"); break;
    case V_NUMBER:  fprintf(fp, "%g", v->as.number); break;
    case V_BOOL:    fprintf(fp, "%s", v->as.boolean ? "true" : "false"); break;
    case V_STRING:  fprintf(fp, "%s", v->as.string); break;
    case V_LIST: {
        fprintf(fp, "[");
        for (int i = 0; i < v->as.list.count; i++) {
            if (i > 0) fprintf(fp, ", ");
            val_print(fp, v->as.list.items[i]);
        }
        fprintf(fp, "]");
        break;
    }
    default: fprintf(fp, "<%d>", v->kind); break;
    }
}

/* ── Stack ─────────────────────────────────────────────────────────── */

#define STACK_MAX 4096
typedef struct {
    Value *slots[STACK_MAX];
    int sp;
} Stack;

static void stack_push(Stack *s, Value *v) { s->slots[s->sp++] = v; }
static Value *stack_pop(Stack *s) { return s->slots[--(s->sp)]; }
static Value *stack_top(Stack *s) { return s->slots[s->sp - 1]; }

/* ── Opcodes (must match bytecode.py) ──────────────────────────────── */

enum {
    OP_NOP = 0, OP_LOAD_CONST = 1, OP_LOAD_NULL = 2, OP_LOAD_TRUE = 3, OP_LOAD_FALSE = 4,
    OP_LOAD_LOCAL = 5, OP_LOAD_GLOBAL = 6, OP_STORE_LOCAL = 7, OP_STORE_GLOBAL = 8,
    OP_POP = 9, OP_DUP = 10,
    OP_JUMP = 20, OP_JUMP_IF_FALSE = 21, OP_JUMP_IF_TRUE = 22,
    OP_CALL = 23, OP_RETURN = 24, OP_BREAK = 25, OP_CONTINUE = 26,
    OP_ADD = 30, OP_SUB = 31, OP_MUL = 32, OP_DIV = 33, OP_MOD = 34,
    OP_EQ = 35, OP_NEQ = 36, OP_LT = 37, OP_GT = 38, OP_LTE = 39, OP_GTE = 40,
    OP_AND = 41, OP_OR = 42,
    OP_NEG = 50, OP_NOT = 51,
    OP_BUILD_RECORD = 60, OP_BUILD_LIST = 61,
    OP_GET_FIELD = 70, OP_SET_FIELD = 71, OP_GET_INDEX = 72, OP_SET_INDEX = 73,
    OP_RECORD_UPDATE = 74,
    OP_TRY_PROPAGATE = 90, OP_REQUIRE = 91,
};

/* ── .mbc deserializer ─────────────────────────────────────────────── */

static uint32_t read_u32(FILE *f) {
    uint8_t b[4]; fread(b, 1, 4, f);
    return b[0] | (b[1]<<8) | (b[2]<<16) | (b[3]<<24);
}

static char *read_string(FILE *f) {
    uint32_t len = read_u32(f);
    char *s = malloc(len + 1);
    fread(s, 1, len, f);
    s[len] = 0;
    return s;
}

typedef struct {
    uint8_t *code;
    int32_t *args;
    int32_t   length;
} Instructions;

static Instructions read_instructions(FILE *f) {
    uint32_t count = read_u32(f);
    uint8_t *code = malloc(count * sizeof(uint8_t));
    int32_t *args = malloc(count * sizeof(int32_t));
    for (uint32_t i = 0; i < count; i++) {
        uint32_t word = read_u32(f);
        code[i] = (uint8_t)(word & 0xFF);
        args[i] = (int32_t)(word >> 8);
    }
    return (Instructions){code, args, (int32_t)count};
}

/* ── VM ─────────────────────────────────────────────────────────────── */

typedef struct {
    Stack   stack;
    Value **globals;
    int32_t global_count;
    char  **global_names;
    Value **locals;
    int32_t local_count;
    char  **local_names;
    Value **constants;
    int32_t const_count;
    Instructions insts;
    int     pc;
    bool    running;
    Value **functions;
    int32_t func_count;
    char  **func_names;
    Instructions *func_insts;
} VM;

static const char *vm_global_name(VM *vm, int idx) {
    if (idx >= 0 && idx < vm->global_count && vm->global_names[idx])
        return vm->global_names[idx];
    return "?";
}

static Value *vm_global(VM *vm, int idx) {
    if (idx >= 0 && idx < vm->global_count) return vm->globals[idx];
    return NULL;
}

static void vm_global_set(VM *vm, int idx, Value *v) {
    if (idx >= 0 && idx < vm->global_count) vm->globals[idx] = v;
}

static Value *vm_local(VM *vm, int idx) {
    if (idx >= 0 && idx < vm->local_count && vm->locals[idx])
        return vm->locals[idx];
    return NULL;
}

static void vm_local_set(VM *vm, int idx, Value *v) {
    if (idx >= 0 && idx < vm->local_count) vm->locals[idx] = v;
}

static Value *vm_const(VM *vm, int idx) {
    if (idx >= 0 && idx < vm->const_count) return vm->constants[idx];
    return NULL;
}

static bool is_truthy(Value *v) {
    if (!v) return false;
    switch (v->kind) {
    case V_NULL:    return false;
    case V_BOOL:    return v->as.boolean;
    case V_NUMBER:  return v->as.number != 0.0;
    case V_STRING:  return strlen(v->as.string) > 0;
    default:        return true;
    }
}

static double to_number(Value *v) {
    if (!v) return 0;
    switch (v->kind) {
    case V_NUMBER: return v->as.number;
    case V_BOOL:   return v->as.boolean ? 1.0 : 0.0;
    case V_STRING: return atof(v->as.string);
    default:       return 0;
    }
}

static void vm_run(VM *vm) {
    vm->pc = 0;
    vm->running = true;
    while (vm->running && vm->pc < vm->insts.length) {
        int op = vm->insts.code[vm->pc];
        int arg = vm->insts.args[vm->pc];
        vm->pc++;

        switch (op) {
        case OP_NOP: break;
        case OP_LOAD_CONST: stack_push(&vm->stack, vm_const(vm, arg)); break;
        case OP_LOAD_NULL:  stack_push(&vm->stack, val_null()); break;
        case OP_LOAD_TRUE:  stack_push(&vm->stack, val_bool(true)); break;
        case OP_LOAD_FALSE: stack_push(&vm->stack, val_bool(false)); break;
        case OP_LOAD_LOCAL:  stack_push(&vm->stack, vm_local(vm, arg)); break;
        case OP_LOAD_GLOBAL: {
            Value *g = vm_global(vm, arg);
            if (!g) { fprintf(stderr, "mossvm: undefined global '%s'\n", vm_global_name(vm, arg)); exit(1); }
            stack_push(&vm->stack, g);
            break;
        }
        case OP_STORE_LOCAL:  vm_local_set(vm, arg, stack_pop(&vm->stack)); break;
        case OP_STORE_GLOBAL: vm_global_set(vm, arg, stack_pop(&vm->stack)); break;
        case OP_POP: { Value *d = stack_pop(&vm->stack); free(d); break; }
        case OP_DUP:  stack_push(&vm->stack, stack_top(&vm->stack)); break;
        case OP_JUMP: vm->pc = arg; break;
        case OP_JUMP_IF_FALSE: {
            Value *cond = stack_pop(&vm->stack);
            if (!is_truthy(cond)) vm->pc = arg;
            break;
        }
        case OP_JUMP_IF_TRUE:
            { Value *cond = stack_pop(&vm->stack); if (is_truthy(cond)) vm->pc = arg; break; }
        case OP_RETURN: vm->running = false; break;
        case OP_CALL: {
            /* Pop args first (reverse order), then callee — matches Python VM */
            Value *fn_args[32] = {0};
            for (int i = arg - 1; i >= 0; i--) fn_args[i] = stack_pop(&vm->stack);
            Value *callee = stack_pop(&vm->stack);
            if (callee && callee->kind == V_STRING) {
                const char *name = callee->as.string;
                if (strcmp(name, "print") == 0) {
                    for (int i = 0; i < arg; i++) {
                        if (i > 0) printf(" ");
                        val_print(stdout, fn_args[i]);
                    }
                    printf("\n"); fflush(stdout);
                    stack_push(&vm->stack, val_null());
                } else if (strcmp(name, "len") == 0) {
                    Value *a = fn_args[0];
                    if (a && a->kind == V_LIST) stack_push(&vm->stack, val_number(a->as.list.count));
                    else if (a && a->kind == V_STRING) stack_push(&vm->stack, val_number(strlen(a->as.string)));
                    else stack_push(&vm->stack, val_number(0));
                } else if (strcmp(name, "assert") == 0) {
                    Value *msg = (arg > 1) ? fn_args[1] : NULL;
                    Value *cond = fn_args[0];
                    if (!is_truthy(cond)) { fprintf(stderr, "mossvm: assertion failed"); if (msg) { fprintf(stderr, ": "); val_print(stderr, msg); } fprintf(stderr, "\n"); exit(1); }
                    stack_push(&vm->stack, val_null());
                }
            }
            break;
        }
        case OP_ADD: {
            Value *r = stack_pop(&vm->stack), *l = stack_pop(&vm->stack);
            if (l->kind == V_STRING || r->kind == V_STRING) {
                char buf[256]; snprintf(buf, sizeof(buf), "%s%s", l->kind == V_STRING ? l->as.string : "", r->kind == V_STRING ? r->as.string : "");
                stack_push(&vm->stack, val_string(buf));
            } else stack_push(&vm->stack, val_number(to_number(l) + to_number(r)));
            break;
        }
        case OP_SUB: { Value *r = stack_pop(&vm->stack), *l = stack_pop(&vm->stack); stack_push(&vm->stack, val_number(to_number(l) - to_number(r))); break; }
        case OP_MUL: { Value *r = stack_pop(&vm->stack), *l = stack_pop(&vm->stack); stack_push(&vm->stack, val_number(to_number(l) * to_number(r))); break; }
        case OP_DIV: { Value *r = stack_pop(&vm->stack), *l = stack_pop(&vm->stack); stack_push(&vm->stack, val_number(to_number(l) / to_number(r))); break; }
        case OP_EQ:  { Value *r = stack_pop(&vm->stack), *l = stack_pop(&vm->stack);
            bool eq = (l->kind == r->kind);
            if (eq && l->kind == V_NUMBER) eq = (l->as.number == r->as.number);
            if (eq && l->kind == V_STRING) eq = (strcmp(l->as.string, r->as.string) == 0);
            if (eq && l->kind == V_BOOL) eq = (l->as.boolean == r->as.boolean);
            if (eq && l->kind == V_NULL) eq = true;
            stack_push(&vm->stack, val_bool(eq)); break;
        }
        case OP_NEQ: { Value *r = stack_pop(&vm->stack), *l = stack_pop(&vm->stack); stack_push(&vm->stack, val_bool(to_number(l) != to_number(r))); break; }
        case OP_LT:  { Value *r = stack_pop(&vm->stack), *l = stack_pop(&vm->stack); stack_push(&vm->stack, val_bool(to_number(l) < to_number(r))); break; }
        case OP_GT:  { Value *r = stack_pop(&vm->stack), *l = stack_pop(&vm->stack); stack_push(&vm->stack, val_bool(to_number(l) > to_number(r))); break; }
        case OP_LTE: { Value *r = stack_pop(&vm->stack), *l = stack_pop(&vm->stack); stack_push(&vm->stack, val_bool(to_number(l) <= to_number(r))); break; }
        case OP_GTE: { Value *r = stack_pop(&vm->stack), *l = stack_pop(&vm->stack); stack_push(&vm->stack, val_bool(to_number(l) >= to_number(r))); break; }
        case OP_NOT: { Value *v = stack_pop(&vm->stack); stack_push(&vm->stack, val_bool(!is_truthy(v))); break; }
        case OP_BUILD_LIST: {
            Value *lst = val_null(); lst->kind = V_LIST;
            lst->as.list.items = calloc(arg, sizeof(Value*));
            lst->as.list.count = arg;
            for (int i = arg - 1; i >= 0; i--) lst->as.list.items[i] = stack_pop(&vm->stack);
            stack_push(&vm->stack, lst); break;
        }
        case OP_GET_FIELD: {
            Value *rec = stack_pop(&vm->stack);
            const char *field = vm_const(vm, arg)->as.string;
            if (rec && rec->kind == V_RECORD) {
                for (int i = 0; i < rec->as.record.count; i++) {
                    if (strcmp(rec->as.record.keys[i], field) == 0) {
                        stack_push(&vm->stack, rec->as.record.vals[i]); break;
                    }
                }
            } else stack_push(&vm->stack, val_null());
            break;
        }
        case OP_TRY_PROPAGATE: {
            Value *v = stack_pop(&vm->stack);
            if (v && v->kind == V_RESULT && !v->as.result.ok) { fprintf(stderr, "mossvm: Err propagation\n"); exit(1); }
            stack_push(&vm->stack, v);
            break;
        }
        default:
            fprintf(stderr, "mossvm: unhandled opcode %d at pc %d\n", op, vm->pc - 1);
            exit(1);
        }
    }
}

/* ── Module loader ──────────────────────────────────────────────────── */

static bool vm_load(VM *vm, const char *path) {
    FILE *f = fopen(path, "rb");
    if (!f) { fprintf(stderr, "mossvm: cannot open %s\n", path); return false; }

    char magic[4]; fread(magic, 1, 4, f);
    if (memcmp(magic, "MOSS", 4) != 0) { fprintf(stderr, "mossvm: bad magic\n"); fclose(f); return false; }
    uint32_t version = read_u32(f);
    (void)version;

    char *module_name = read_string(f);       free(module_name);
    char *source_path = read_string(f);       free(source_path);

    /* globals */
    vm->global_count = (int32_t)read_u32(f);
    vm->globals = calloc(vm->global_count, sizeof(Value*));
    vm->global_names = calloc(vm->global_count, sizeof(char*));
    for (int i = 0; i < vm->global_count; i++) vm->global_names[i] = read_string(f);

    /* effects */ { uint32_t n = read_u32(f); for (uint32_t i = 0; i < n; i++) free(read_string(f)); }
    /* imports */  { uint32_t n = read_u32(f); for (uint32_t i = 0; i < n; i++) free(read_string(f)); }
    /* tests */    { uint32_t n = read_u32(f); for (uint32_t i = 0; i < n; i++) free(read_string(f)); }

    /* code object */
    char *co_name = read_string(f);
    int32_t co_argc = (int32_t)read_u32(f);
    int32_t co_capc = (int32_t)read_u32(f);
    uint8_t is_rule_byte; fread(&is_rule_byte, 1, 1, f); (void)is_rule_byte;
    int32_t co_srcl = (int32_t)read_u32(f);
    int32_t co_srcc = (int32_t)read_u32(f);

    vm->local_count = (int32_t)read_u32(f);
    vm->locals = calloc(vm->local_count, sizeof(Value*));
    vm->local_names = calloc(vm->local_count, sizeof(char*));
    for (int i = 0; i < vm->local_count; i++) vm->local_names[i] = read_string(f);

    /* constants (JSON) */ {
        uint32_t c_len = read_u32(f);
        char *c_json = malloc(c_len + 1);
        fread(c_json, 1, c_len, f); c_json[c_len] = 0;
        /* simplistic JSON parse: just extract strings/numbers */
        vm->const_count = 0;
        for (uint32_t i = 0; i < c_len; i++) if (c_json[i] == ',') vm->const_count++;
        vm->const_count++; /* at least one */
        vm->constants = calloc(vm->const_count, sizeof(Value*));
        int ci = 0;
        char *p = c_json;
        while (*p && ci < vm->const_count) {
            while (*p == ' ' || *p == '[' || *p == ']' || *p == ',') p++;
            if (*p == '"') { p++; char *start = p; while (*p && *p != '"') p++; *p = 0; p++; vm->constants[ci++] = val_string(start); }
            else if (*p == '-' || (*p >= '0' && *p <= '9')) { vm->constants[ci++] = val_number(atof(p)); while (*p && *p != ',' && *p != ']') p++; }
            else if (*p == 'n' && strncmp(p, "null", 4) == 0) { vm->constants[ci++] = val_null(); p += 4; }
            else if (*p == 't' && strncmp(p, "true", 4) == 0)  { vm->constants[ci++] = val_bool(true); p += 4; }
            else if (*p == 'f' && strncmp(p, "false", 5) == 0) { vm->constants[ci++] = val_bool(false); p += 5; }
            else p++;
        }
        vm->const_count = ci;
        free(c_json);
    }
    free(co_name);

    /* instructions */
    vm->insts = read_instructions(f);
    vm->pc = 0;

    /* functions */
    vm->func_count = (int32_t)read_u32(f);
    vm->functions = calloc(vm->func_count, sizeof(Value*));
    vm->func_names = calloc(vm->func_count, sizeof(char*));
    vm->func_insts = calloc(vm->func_count, sizeof(Instructions));
    for (int i = 0; i < vm->func_count; i++) {
        char *fn_name = read_string(f);
        vm->func_names[i] = fn_name;
        /* register as global callable */
        Value *fn_val = val_string(fn_name);
        /* Now read + skip code object metadata + instructions */
        read_u32(f); /* arg_count */
        read_u32(f); /* cap_count */
        { uint8_t dummy; fread(&dummy, 1, 1, f); } /* is_rule (1 byte) */
        read_u32(f); /* source_line */
        read_u32(f); /* source_column */
        uint32_t nl = read_u32(f); for (uint32_t j = 0; j < nl; j++) free(read_string(f));
        uint32_t ncj = read_u32(f); fseek(f, ncj, SEEK_CUR); /* skip constants */
        vm->func_insts[i] = read_instructions(f);
        vm->functions[i] = fn_val;
    }

    fclose(f);
    return true;
}

/* ── Boot builtins ──────────────────────────────────────────────────── */

static void vm_boot_builtins(VM *vm) {
    for (int i = 0; i < vm->global_count; i++) {
        if (vm->global_names[i] && strcmp(vm->global_names[i], "print") == 0)
            vm->globals[i] = val_string("print");
    }
}

/* ── Main ──────────────────────────────────────────────────────────── */

int main(int argc, char *argv[]) {
    if (argc < 2) { fprintf(stderr, "usage: mossvm program.mbc\n"); return 1; }

    VM vm = {0};
    if (!vm_load(&vm, argv[1])) return 1;
    vm_boot_builtins(&vm);
    vm_run(&vm);
    return 0;
}
