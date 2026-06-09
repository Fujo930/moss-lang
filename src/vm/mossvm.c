/* Moss VM — portable C implementation of the Moss bytecode virtual machine.
 *
 * Build:  cc -o mossvm mossvm.c -lm
 * Usage:  mossvm program.mbc
 *
 * Reads the .mbc binary format, deserializes the bytecode module, and
 * executes it on a stack-based VM.  All 32 opcodes from the Moss
 * instruction set are supported.
 *
 * v0.59.0 — Reasonix, 2026
 */

#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <stdbool.h>
#ifdef _WIN32
#include <windows.h>
#else
#include <unistd.h>
#endif

/* strndup polyfill for C99 (POSIX function) */
static char *strndup(const char *s, size_t n) {
    size_t len = strlen(s);
    if (len > n) len = n;
    char *buf = malloc(len + 1);
    if (buf) { memcpy(buf, s, len); buf[len] = 0; }
    return buf;
}

/* ── Value types ──────────────────────────────────────────────────── */

typedef enum { V_NULL, V_NUMBER, V_BOOL, V_STRING, V_LIST, V_RECORD, V_VARIANT, V_RESULT, V_CODE, V_MONEY } ValueKind;

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
            double amount;
            char *currency;
        } money;
        struct {
            uint8_t  *instructions;
            int32_t  *args;
            int32_t   length;
            int32_t   local_count;
            char    **local_names;
        } code;
    } as;
} Value;

static Value *val_null(void);
static Value *val_number(double n);
static Value *val_bool(bool b);

static Value *val_money(double amount, const char *currency);
static Value *val_string(const char *s);

static Value *val_variant(const char *name) {
    Value *v = calloc(1, sizeof(Value));
    v->kind = V_VARIANT;
    v->as.variant.name = strdup(name);
    v->as.variant.payload = NULL;
    return v;
}

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

static Value *val_money(double amount, const char *currency) {
    Value *v = calloc(1, sizeof(Value));
    v->kind = V_MONEY;
    v->as.money.amount = amount;
    v->as.money.currency = strdup(currency);
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
    case V_NUMBER: { char buf[32]; double d = v->as.number; if (d == (int)d) snprintf(buf, sizeof(buf), "%d", (int)d); else { snprintf(buf, sizeof(buf), "%g", d); } fprintf(fp, "%s", buf); break; }
    case V_BOOL:    fprintf(fp, "%s", v->as.boolean ? "true" : "false"); break;
    case V_STRING:  fprintf(fp, "%s", v->as.string); break;
    case V_RESULT: fprintf(fp, "%s(", v->as.result.ok ? "Ok" : "Err"); val_print(fp, v->as.result.value); fprintf(fp, ")"); break;
    case V_VARIANT: fprintf(fp, "%s", v->as.variant.name);
                    if (v->as.variant.payload) { fprintf(fp, "("); val_print(fp, v->as.variant.payload); fprintf(fp, ")"); }
                    break;
    case V_MONEY:   fprintf(fp, "%g.%s", v->as.money.amount, v->as.money.currency); break;
    case V_RECORD: {
        fprintf(fp, "{");
        for (int i = 0; i < v->as.record.count; i++) {
            if (i > 0) fprintf(fp, ", ");
            fprintf(fp, "%s: ", v->as.record.keys[i]);
            val_print(fp, v->as.record.vals[i]);
        }
        fprintf(fp, "}");
        break;
    }
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
#define MAX_FRAME_DEPTH 1000
#define MAX_STRING_LEN (1024 * 1024)  /* 1 MB */
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
    OP_TRY_PROPAGATE = 95, OP_REQUIRE = 92,
    OP_CHECK_EFFECT = 100,
    OP_CALL_PYTHON = 110,
};

/* ── .mbc deserializer ─────────────────────────────────────────────── */

static uint32_t read_u32(FILE *f) {
    uint8_t b[4]; fread(b, 1, 4, f);
    return b[0] | (b[1]<<8) | (b[2]<<16) | (b[3]<<24);
}

static char *read_string(FILE *f) {
    uint32_t len = read_u32(f);
    if (len > MAX_STRING_LEN) { fprintf(stderr, "mossvm: string too long (%u bytes)\n", len); exit(1); }
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
        code[i] = (uint8_t)fgetc(f);             /* opcode: 1 byte */
        args[i] = (int32_t)read_u32(f);           /* arg: 4 bytes */
        read_u32(f);                              /* line: 4 bytes (skip) */
        uint16_t col; fread(&col, 1, 2, f);       /* column: 2 bytes (skip) */
        (void)col;
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
    /* Call frame stack for Moss function calls */
    struct {
        int       saved_pc;
        Value   **saved_locals;
        int32_t   saved_local_count;
        char    **saved_local_names;
        Value   **saved_constants;
        int32_t   saved_const_count;
        Instructions saved_insts;
    } frames[256];
    int     frame_depth;
    /* Simple in-memory DB */
    char  **db_keys;
    Value **db_vals;
    int     db_count;
} VM;

/* Function registry for Moss-defined functions */
#define MAX_FUNCS 512
static struct { char *name; Instructions insts; int arg_count; int local_count; char **local_names; Value **constants; int const_count; } *func_registry = NULL;
static int func_registry_count = 0;

static void vm_register_func(const char *name, Instructions insts, int arg_count,
                              int local_count, char **local_names,
                              Value **constants, int const_count) {
    if (!func_registry) func_registry = calloc(MAX_FUNCS, sizeof(*func_registry));
    int idx = func_registry_count++;
    func_registry[idx].name = strdup(name);
    func_registry[idx].insts = insts;
    func_registry[idx].arg_count = arg_count;
    func_registry[idx].local_count = local_count;
    func_registry[idx].local_names = local_names;
    func_registry[idx].constants = constants;
    func_registry[idx].const_count = const_count;
}

static int vm_find_func(const char *name) {
    if (!func_registry) return -1;
    for (int i = 0; i < func_registry_count; i++)
        if (func_registry[i].name && strcmp(func_registry[i].name, name) == 0) return i;
    return -1;
}

static const char *vm_global_name(VM *vm, int idx) {
    if (idx >= 0 && idx < vm->global_count && vm->global_names[idx])
        return vm->global_names[idx];
    return NULL;
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
    case V_MONEY:  return v->as.money.amount;
    default:       return 0;
    }
}

static Value *vm_resolve_global(VM *vm, int idx);

static void vm_db_put(VM *vm, const char *key, Value *val) {
    for (int i = 0; i < vm->db_count; i++)
        if (strcmp(vm->db_keys[i], key) == 0) { vm->db_vals[i] = val; return; }
    vm->db_keys = realloc(vm->db_keys, (vm->db_count+1)*sizeof(char*));
    vm->db_vals = realloc(vm->db_vals, (vm->db_count+1)*sizeof(Value*));
    vm->db_keys[vm->db_count] = strdup(key);
    vm->db_vals[vm->db_count] = val;
    vm->db_count++;
}
static Value *vm_db_get(VM *vm, const char *key) {
    for (int i = 0; i < vm->db_count; i++)
        if (strcmp(vm->db_keys[i], key) == 0) return vm->db_vals[i];
    return val_null();
}

static void vm_run(VM *vm) {
    vm->pc = 0;
    vm->running = true;
    int steps = 0;
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
            Value *g = vm_resolve_global(vm, arg);
            if (!g) {
                const char *gn = vm_global_name(vm, arg);
                fprintf(stderr, "mossvm: undefined global '%s' at %d\n", gn ? gn : "?", arg);
                exit(1);
            }
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
        case OP_RETURN:
            if (vm->frame_depth > 0) {
                Value *ret = vm->stack.sp > 0 ? stack_pop(&vm->stack) : val_null();
                vm->frame_depth--;
                vm->pc          = vm->frames[vm->frame_depth].saved_pc;
                vm->locals      = vm->frames[vm->frame_depth].saved_locals;
                vm->local_count = vm->frames[vm->frame_depth].saved_local_count;
                vm->local_names = vm->frames[vm->frame_depth].saved_local_names;
                vm->constants   = vm->frames[vm->frame_depth].saved_constants;
                vm->const_count = vm->frames[vm->frame_depth].saved_const_count;
                vm->insts       = vm->frames[vm->frame_depth].saved_insts;
                stack_push(&vm->stack, ret);
            } else {
                vm->running = false;
            }
            break;
        case OP_CALL: {
            Value *fn_args[32] = {0};
            for (int i = arg - 1; i >= 0; i--) fn_args[i] = stack_pop(&vm->stack);
            Value *callee = stack_pop(&vm->stack);
            if (!callee) { stack_push(&vm->stack, val_null()); break; }
            if (callee->kind == V_STRING) {
                    const char *name = callee->as.string;
                    if (strcmp(name, "print") == 0) {
                        for (int i = 0; i < arg; i++) { if(i>0)printf(" "); val_print(stdout, fn_args[i]); }
                        printf("\n"); fflush(stdout);
                        stack_push(&vm->stack, val_null());
                    } else if (strcmp(name, "len") == 0) {
                        Value *a = fn_args[0];
                        if (a && a->kind == V_LIST) stack_push(&vm->stack, val_number(a->as.list.count));
                        else if (a && a->kind == V_STRING) stack_push(&vm->stack, val_number(strlen(a->as.string)));
                        else stack_push(&vm->stack, val_number(0));
                    } else if (strcmp(name, "assert") == 0) {
                        Value *msg = (arg > 1) ? fn_args[1] : NULL;
                        if (!is_truthy(fn_args[0])) { fprintf(stderr, "mossvm: assert failed"); if(msg){fprintf(stderr,": ");val_print(stderr,msg);} fprintf(stderr,"\n"); exit(1); }
                        stack_push(&vm->stack, val_null());
                    } else if (strcmp(name, "dbPut") == 0) {
                        if (arg >= 2 && fn_args[0] && fn_args[0]->kind == V_STRING) {
                            vm_db_put(vm, fn_args[0]->as.string, fn_args[1]);
                            stack_push(&vm->stack, fn_args[1]);
                        } else stack_push(&vm->stack, val_null());
                    } else if (strcmp(name, "dbGet") == 0) {
                        if (arg >= 1 && fn_args[0] && fn_args[0]->kind == V_STRING)
                            stack_push(&vm->stack, vm_db_get(vm, fn_args[0]->as.string));
                        else stack_push(&vm->stack, val_null());
                    } else if (strcmp(name, "range") == 0) {
                        Value *lst = val_null(); lst->kind = V_LIST;
                        double s=0, e=0;
                        if (arg >= 2) { s=to_number(fn_args[0]); e=to_number(fn_args[1]); }
                        else if (arg >= 1) e=to_number(fn_args[0]);
                        int n = (int)(e - s); if(n<0)n=0;
                        lst->as.list.items = calloc(n, sizeof(Value*));
                        lst->as.list.count = n;
                        for (int i=0;i<n;i++) lst->as.list.items[i]=val_number(s+i);
                        stack_push(&vm->stack, lst);
                    } else if (strcmp(name, "listNew") == 0) {
                        Value *lst = val_null(); lst->kind = V_LIST;
                        lst->as.list.items = NULL; lst->as.list.count = 0;
                        stack_push(&vm->stack, lst);
                    } else if (strcmp(name, "listPush") == 0) {
                        Value *lst = (arg>=2)?fn_args[0]:NULL;
                        Value *item = (arg>=2)?fn_args[1]:fn_args[0];
                        if (lst && lst->kind == V_LIST) {
                            lst->as.list.items = realloc(lst->as.list.items, (lst->as.list.count+1)*sizeof(Value*));
                            lst->as.list.items[lst->as.list.count++] = item;
                            stack_push(&vm->stack, lst);
                        } else stack_push(&vm->stack, val_null());
                    } else if (strcmp(name, "listGet") == 0) {
                        Value *lst = fn_args[0]; int idx = (int)to_number(fn_args[1]);
                        if (lst && lst->kind == V_LIST && idx>=0 && idx<lst->as.list.count)
                            stack_push(&vm->stack, lst->as.list.items[idx]);
                        else stack_push(&vm->stack, (arg>=3)?fn_args[2]:val_null());
                    } else if (strcmp(name, "textJoin") == 0) {
                        Value *sep = fn_args[0];
                        Value *parts = (arg>=2) ? fn_args[1] : NULL;
                        if (arg==1) { sep = val_string(""); parts = fn_args[0]; }
                        char buf[4096] = ""; int pos = 0;
                        if (parts && parts->kind == V_LIST && sep && sep->kind == V_STRING) {
                            for (int i = 0; i < parts->as.list.count; i++) {
                                if (i > 0) pos += snprintf(buf+pos, sizeof(buf)-pos, "%s", sep->as.string);
                                if (parts->as.list.items[i] && parts->as.list.items[i]->kind == V_STRING)
                                    pos += snprintf(buf+pos, sizeof(buf)-pos, "%s", parts->as.list.items[i]->as.string);
                            }
                        }
                        stack_push(&vm->stack, val_string(buf));
                    } else if (strcmp(name, "textChars") == 0) {
                        if (fn_args[0] && fn_args[0]->kind == V_STRING) {
                            Value *lst = val_null(); lst->kind = V_LIST;
                            const char *s = fn_args[0]->as.string;
                            int n = (int)strlen(s);
                            lst->as.list.items = calloc(n, sizeof(Value*));
                            lst->as.list.count = n;
                            for (int i=0;i<n;i++) { char ch[2]={s[i],0}; lst->as.list.items[i]=val_string(ch); }
                            stack_push(&vm->stack, lst);
                        } else stack_push(&vm->stack, val_null());
                    } else if (strcmp(name, "textReplace") == 0) {
                        if (arg>=3 && fn_args[0] && fn_args[0]->kind == V_STRING) {
                            const char *s=fn_args[0]->as.string, *old=fn_args[1]->as.string, *nw=fn_args[2]->as.string;
                            char buf[2048]=""; int pos=0;
                            const char *p=s; int olen=(int)strlen(old);
                            while (*p) {
                                if (strncmp(p,old,olen)==0) { pos+=snprintf(buf+pos,sizeof(buf)-pos,"%s",nw); p+=olen; }
                                else buf[pos++]=*p++;
                            }
                            buf[pos]=0;
                            stack_push(&vm->stack, val_string(buf));
                        } else stack_push(&vm->stack, val_null());
                    } else if (strcmp(name, "readText") == 0) {
                        if (fn_args[0] && fn_args[0]->kind == V_STRING) {
                            FILE *rf = fopen(fn_args[0]->as.string, "r");
                            if (rf) { fseek(rf,0,SEEK_END); long sz=ftell(rf); fseek(rf,0,SEEK_SET);
                                if (sz > MAX_STRING_LEN) { fclose(rf); fprintf(stderr, "mossvm: file too large (%ld bytes, max %d)\n", sz, MAX_STRING_LEN); stack_push(&vm->stack, val_string("")); }
                                else { char *buf=malloc(sz+1); fread(buf,1,sz,rf); buf[sz]=0; fclose(rf);
                                stack_push(&vm->stack, val_string(buf)); free(buf); } }
                            else stack_push(&vm->stack, val_string(""));
                        } else stack_push(&vm->stack, val_null());
                    } else if (strcmp(name, "fileExists") == 0) {
                        if (fn_args[0] && fn_args[0]->kind == V_STRING) {
                            FILE *tf = fopen(fn_args[0]->as.string, "r");
                            stack_push(&vm->stack, val_bool(tf != NULL));
                            if (tf) fclose(tf);
                        } else stack_push(&vm->stack, val_bool(false));
                    } else if (strcmp(name, "textTrim") == 0) {
                        if (fn_args[0] && fn_args[0]->kind == V_STRING) {
                            const char *s = fn_args[0]->as.string;
                            while (*s == ' ' || *s == '\t' || *s == '\n' || *s == '\r') s++;
                            const char *e = s + strlen(s);
                            while (e > s && (e[-1] == ' ' || e[-1] == '\t' || e[-1] == '\n' || e[-1] == '\r')) e--;
                            char *buf = strndup(s, e - s);
                            stack_push(&vm->stack, val_string(buf));
                            free(buf);
                        } else stack_push(&vm->stack, val_null());
                    } else if (strcmp(name, "textSlice") == 0) {
                        if (arg >= 3 && fn_args[0] && fn_args[0]->kind == V_STRING) {
                            const char *s = fn_args[0]->as.string;
                            int start = (int)to_number(fn_args[1]);
                            int end = (int)to_number(fn_args[2]);
                            int slen = (int)strlen(s);
                            if (start < 0) start = slen + start;
                            if (end < 0) end = slen + end;
                            if (start < 0) start = 0;
                            if (end > slen) end = slen;
                            if (start > end) { stack_push(&vm->stack, val_string("")); }
                            else { char *buf = strndup(s + start, end - start);
                                stack_push(&vm->stack, val_string(buf)); free(buf); }
                        } else stack_push(&vm->stack, val_null());
                    } else if (strcmp(name, "textContains") == 0) {
                        stack_push(&vm->stack,
                            (arg >= 2 && fn_args[0] && fn_args[0]->kind == V_STRING && fn_args[1] && fn_args[1]->kind == V_STRING)
                            ? val_bool(strstr(fn_args[0]->as.string, fn_args[1]->as.string) != NULL)
                            : val_bool(false));
                    } else if (strcmp(name, "textStartsWith") == 0) {
                        stack_push(&vm->stack,
                            (arg >= 2 && fn_args[0] && fn_args[0]->kind == V_STRING && fn_args[1] && fn_args[1]->kind == V_STRING)
                            ? val_bool(strncmp(fn_args[0]->as.string, fn_args[1]->as.string, strlen(fn_args[1]->as.string)) == 0)
                            : val_bool(false));
                    } else if (strcmp(name, "textEndsWith") == 0) {
                        if (arg >= 2 && fn_args[0] && fn_args[0]->kind == V_STRING && fn_args[1] && fn_args[1]->kind == V_STRING) {
                            const char *s = fn_args[0]->as.string, *suffix = fn_args[1]->as.string;
                            int slen = strlen(s), sulen = strlen(suffix);
                            stack_push(&vm->stack, val_bool(slen >= sulen && strcmp(s + slen - sulen, suffix) == 0));
                        } else stack_push(&vm->stack, val_bool(false));
                    } else if (strcmp(name, "textIndexOf") == 0) {
                        if (arg >= 2 && fn_args[0] && fn_args[0]->kind == V_STRING && fn_args[1] && fn_args[1]->kind == V_STRING) {
                            const char *found = strstr(fn_args[0]->as.string, fn_args[1]->as.string);
                            stack_push(&vm->stack, found ? val_number(found - fn_args[0]->as.string) : val_number(-1));
                        } else stack_push(&vm->stack, val_number(-1));
                    } else if (strcmp(name, "textSplit") == 0) {
                        if (arg >= 2 && fn_args[0] && fn_args[0]->kind == V_STRING && fn_args[1] && fn_args[1]->kind == V_STRING) {
                            const char *s = fn_args[0]->as.string, *sep = fn_args[1]->as.string;
                            Value *lst = val_null(); lst->kind = V_LIST;
                            lst->as.list.items = calloc(strlen(s) + 1, sizeof(Value*));
                            int cnt = 0;
                            const char *p = s;
                            int seplen = (int)strlen(sep);
                            if (seplen == 0) {
                                for (int i = 0; s[i]; i++) lst->as.list.items[cnt++] = val_string((char[]){s[i],0});
                            } else {
                                while (*p) {
                                    const char *nxt = strstr(p, sep);
                                    if (nxt) {
                                        lst->as.list.items[cnt++] = val_string(strndup(p, nxt - p));
                                        p = nxt + seplen;
                                    } else {
                                        lst->as.list.items[cnt++] = val_string(p);
                                        break;
                                    }
                                }
                            }
                            lst->as.list.count = cnt;
                            stack_push(&vm->stack, lst);
                        } else stack_push(&vm->stack, val_null());
                    } else if (strcmp(name, "mapNew") == 0) {
                        Value *m = val_null(); m->kind = V_RECORD;
                        m->as.record.keys = NULL; m->as.record.vals = NULL; m->as.record.count = 0;
                        stack_push(&vm->stack, m);
                    } else if (strcmp(name, "mapPut") == 0) {
                        if (arg >= 3 && fn_args[0] && fn_args[0]->kind == V_RECORD && fn_args[1] && fn_args[1]->kind == V_STRING) {
                            Value *m = fn_args[0]; bool fnd = false;
                            for (int i = 0; i < m->as.record.count; i++)
                                if (strcmp(m->as.record.keys[i], fn_args[1]->as.string) == 0)
                                    { m->as.record.vals[i] = fn_args[2]; fnd = true; break; }
                            if (!fnd) {
                                m->as.record.keys = realloc(m->as.record.keys, (m->as.record.count+1)*sizeof(char*));
                                m->as.record.vals = realloc(m->as.record.vals, (m->as.record.count+1)*sizeof(Value*));
                                m->as.record.keys[m->as.record.count] = strdup(fn_args[1]->as.string);
                                m->as.record.vals[m->as.record.count] = fn_args[2];
                                m->as.record.count++;
                            }
                            stack_push(&vm->stack, m);
                        } else stack_push(&vm->stack, val_null());
                    } else if (strcmp(name, "mapGet") == 0) {
                        if (arg >= 2 && fn_args[0] && fn_args[0]->kind == V_RECORD && fn_args[1] && fn_args[1]->kind == V_STRING) {
                            for (int i = 0; i < fn_args[0]->as.record.count; i++)
                                if (strcmp(fn_args[0]->as.record.keys[i], fn_args[1]->as.string) == 0)
                                    { stack_push(&vm->stack, fn_args[0]->as.record.vals[i]); break; }
                            stack_push(&vm->stack, (arg >= 3) ? fn_args[2] : val_null());
                        } else stack_push(&vm->stack, val_null());
                    } else if (strcmp(name, "mapHas") == 0) {
                        bool found = false;
                        if (arg >= 2 && fn_args[0] && fn_args[0]->kind == V_RECORD && fn_args[1] && fn_args[1]->kind == V_STRING)
                            for (int i = 0; i < fn_args[0]->as.record.count; i++)
                                if (strcmp(fn_args[0]->as.record.keys[i], fn_args[1]->as.string) == 0) { found = true; break; }
                        stack_push(&vm->stack, val_bool(found));
                    } else if (strcmp(name, "mapKeys") == 0) {
                        Value *lst = val_null(); lst->kind = V_LIST;
                        if (arg >= 1 && fn_args[0] && fn_args[0]->kind == V_RECORD) {
                            lst->as.list.count = fn_args[0]->as.record.count;
                            lst->as.list.items = calloc(lst->as.list.count, sizeof(Value*));
                            for (int i = 0; i < lst->as.list.count; i++)
                                lst->as.list.items[i] = val_string(fn_args[0]->as.record.keys[i]);
                        }
                        stack_push(&vm->stack, lst);
                    } else if (strcmp(name, "mapValues") == 0) {
                        Value *lst = val_null(); lst->kind = V_LIST;
                        if (arg >= 1 && fn_args[0] && fn_args[0]->kind == V_RECORD) {
                            lst->as.list.count = fn_args[0]->as.record.count;
                            lst->as.list.items = calloc(lst->as.list.count, sizeof(Value*));
                            for (int i = 0; i < lst->as.list.count; i++)
                                lst->as.list.items[i] = fn_args[0]->as.record.vals[i];
                        }
                        stack_push(&vm->stack, lst);
                    } else if (strcmp(name, "mapRemove") == 0) {
                        if (arg >= 2 && fn_args[0] && fn_args[0]->kind == V_RECORD && fn_args[1] && fn_args[1]->kind == V_STRING) {
                            Value *m = fn_args[0];
                            int idx = -1;
                            for (int i = 0; i < m->as.record.count; i++)
                                if (strcmp(m->as.record.keys[i], fn_args[1]->as.string) == 0) { idx = i; break; }
                            if (idx >= 0) {
                                free(m->as.record.keys[idx]);
                                for (int i = idx; i < m->as.record.count - 1; i++) { m->as.record.keys[i] = m->as.record.keys[i+1]; m->as.record.vals[i] = m->as.record.vals[i+1]; }
                                m->as.record.count--;
                            }
                            stack_push(&vm->stack, m);
                        } else stack_push(&vm->stack, val_null());
                    } else if (strcmp(name, "jsonStringify") == 0) {
                        char buf[4096] = "";
                        if (arg >= 1 && fn_args[0]) {
                            FILE *tmpf = tmpfile();
                            if (tmpf) { val_print(tmpf, fn_args[0]); fflush(tmpf); long sz = ftell(tmpf); fseek(tmpf, 0, SEEK_SET); fread(buf, 1, sz < 4095 ? sz : 4095, tmpf); buf[sz<4095?sz:4095] = 0; fclose(tmpf); }
                        }
                        stack_push(&vm->stack, val_string(buf));
                    } else if (strcmp(name, "jsonParse") == 0) {
                        /* Simple JSON parse: just return the string as-is for now */
                        if (arg >= 1 && fn_args[0] && fn_args[0]->kind == V_STRING)
                            stack_push(&vm->stack, val_string(fn_args[0]->as.string));
                        else stack_push(&vm->stack, val_null());
                    } else if (strcmp(name, "writeText") == 0) {
                        if (arg >= 2 && fn_args[0] && fn_args[0]->kind == V_STRING && fn_args[1] && fn_args[1]->kind == V_STRING) {
                            FILE *wf = fopen(fn_args[0]->as.string, "w");
                            if (wf) { fputs(fn_args[1]->as.string, wf); fclose(wf); stack_push(&vm->stack, fn_args[1]); }
                            else stack_push(&vm->stack, val_null());
                        } else stack_push(&vm->stack, val_null());
                    } else if (strcmp(name, "listFiles") == 0) {
                        /* Return empty list on Windows — directory listing needs platform code */
                        Value *lst = val_null(); lst->kind = V_LIST;
                        lst->as.list.items = NULL; lst->as.list.count = 0;
#ifdef __unix__
                        if (arg >= 1 && fn_args[0] && fn_args[0]->kind == V_STRING) {
                            FILE *pp = popen("ls", "r"); /* simplified */
                            if (pp) { /* TODO: real directory listing */ pclose(pp); }
                        }
#endif
                        stack_push(&vm->stack, lst);
                    } else if (strcmp(name, "listSet") == 0) {
                        if (arg >= 3 && fn_args[0] && fn_args[0]->kind == V_LIST) {
                            int idx = (int)to_number(fn_args[1]);
                            if (idx >= 0 && idx < fn_args[0]->as.list.count)
                                fn_args[0]->as.list.items[idx] = fn_args[2];
                            stack_push(&vm->stack, fn_args[0]);
                        } else stack_push(&vm->stack, val_null());
                    } else if (strcmp(name, "listSlice") == 0) {
                        if (arg >= 3 && fn_args[0] && fn_args[0]->kind == V_LIST) {
                            int start = (int)to_number(fn_args[1]);
                            int end = (int)to_number(fn_args[2]);
                            Value *lst = val_null(); lst->kind = V_LIST;
                            int cnt = fn_args[0]->as.list.count;
                            if (start < 0) start = cnt + start;
                            if (end < 0) end = cnt + end;
                            if (start < 0) start = 0;
                            if (end > cnt) end = cnt;
                            int n = (end > start) ? end - start : 0;
                            lst->as.list.items = calloc(n, sizeof(Value*));
                            lst->as.list.count = n;
                            for (int i = 0; i < n; i++) lst->as.list.items[i] = fn_args[0]->as.list.items[start + i];
                            stack_push(&vm->stack, lst);
                        } else stack_push(&vm->stack, val_null());
                    } else if (strcmp(name, "listConcat") == 0) {
                        Value *lst = val_null(); lst->kind = V_LIST;
                        int total = 0;
                        for (int i = 0; i < arg; i++)
                            if (fn_args[i] && fn_args[i]->kind == V_LIST) total += fn_args[i]->as.list.count;
                        lst->as.list.items = calloc(total, sizeof(Value*));
                        lst->as.list.count = total;
                        int pos = 0;
                        for (int i = 0; i < arg; i++)
                            if (fn_args[i] && fn_args[i]->kind == V_LIST)
                                for (int j = 0; j < fn_args[i]->as.list.count; j++)
                                    lst->as.list.items[pos++] = fn_args[i]->as.list.items[j];
                        stack_push(&vm->stack, lst);
                    } else if (strcmp(name, "listInsert") == 0) {
                        if (arg >= 3 && fn_args[0] && fn_args[0]->kind == V_LIST) {
                            Value *lst = fn_args[0];
                            int idx = (int)to_number(fn_args[1]);
                            if (idx < 0) idx = lst->as.list.count + idx;
                            if (idx < 0) idx = 0;
                            if (idx > lst->as.list.count) idx = lst->as.list.count;
                            lst->as.list.items = realloc(lst->as.list.items, (lst->as.list.count+1)*sizeof(Value*));
                            for (int i = lst->as.list.count; i > idx; i--) lst->as.list.items[i] = lst->as.list.items[i-1];
                            lst->as.list.items[idx] = fn_args[2];
                            lst->as.list.count++;
                            stack_push(&vm->stack, lst);
                        } else stack_push(&vm->stack, val_null());
                    } else if (strcmp(name, "listRemove") == 0) {
                        if (arg >= 2 && fn_args[0] && fn_args[0]->kind == V_LIST) {
                            Value *lst = fn_args[0];
                            int idx = (int)to_number(fn_args[1]);
                            if (idx < 0) idx = lst->as.list.count + idx;
                            if (idx >= 0 && idx < lst->as.list.count) {
                                for (int i = idx; i < lst->as.list.count - 1; i++) lst->as.list.items[i] = lst->as.list.items[i+1];
                                lst->as.list.count--;
                            }
                            stack_push(&vm->stack, lst);
                        } else stack_push(&vm->stack, val_null());
                    } else if (strcmp(name, "httpGet") == 0 || strcmp(name, "httpPostJson") == 0) {
                        stack_push(&vm->stack, val_string("{}"));
                    } else if (strcmp(name, "processRun") == 0 || strcmp(name, "processRunJson") == 0) {
                        stack_push(&vm->stack, val_string("{}"));
                    } else if (name[0] >= 'A' && name[0] <= 'Z') {
                        /* Ok(value) → Result, Err(value) → Result, others → Variant */
                        Value *r = val_null();
                        if (strcmp(name, "Ok") == 0) {
                            r->kind = V_RESULT; r->as.result.ok = true;
                            r->as.result.value = (arg > 0) ? fn_args[0] : val_null();
                        } else if (strcmp(name, "Err") == 0) {
                            r->kind = V_RESULT; r->as.result.ok = false;
                            r->as.result.value = (arg > 0) ? fn_args[0] : val_null();
                        } else {
                            r->kind = V_VARIANT; r->as.variant.name = strdup(name);
                            r->as.variant.payload = (arg > 0) ? fn_args[0] : NULL;
                        }
                        stack_push(&vm->stack, r);
                    } else {
                        /* Moss-defined function */
                        int fi = vm_find_func(name);
                        if (fi >= 0 && vm->frame_depth < (MAX_FRAME_DEPTH - 1)) {
                            vm->frames[vm->frame_depth].saved_pc           = vm->pc;
                            vm->frames[vm->frame_depth].saved_locals       = vm->locals;
                            vm->frames[vm->frame_depth].saved_local_count  = vm->local_count;
                            vm->frames[vm->frame_depth].saved_local_names  = vm->local_names;
                            vm->frames[vm->frame_depth].saved_constants    = vm->constants;
                            vm->frames[vm->frame_depth].saved_const_count  = vm->const_count;
                            vm->frames[vm->frame_depth].saved_insts        = vm->insts;
                            vm->frame_depth++;
                            vm->insts       = func_registry[fi].insts;
                            vm->constants   = func_registry[fi].constants;
                            vm->const_count = func_registry[fi].const_count;
                            vm->local_count = func_registry[fi].local_count;
                            vm->local_names = func_registry[fi].local_names;
                            vm->locals      = calloc(vm->local_count, sizeof(Value*));
                            for (int ai = 0; ai < arg && ai < vm->local_count; ai++)
                                vm->locals[ai] = fn_args[ai];
                            vm->pc = 0;
                        } else if (fi >= 0 && vm->frame_depth >= (MAX_FRAME_DEPTH - 1)) {
                            fprintf(stderr, "mossvm: stack overflow — max call depth %d exceeded at '%s'\n", MAX_FRAME_DEPTH, name);
                            exit(1);
                        } else stack_push(&vm->stack, val_null());
                    }
            } else if (callee->kind == V_VARIANT && callee->as.variant.name) {
                const char *vn = callee->as.variant.name;
                Value *res = val_null(); res->kind = V_RESULT;
                if (strcmp(vn, "Ok") == 0) { res->as.result.ok = true; res->as.result.value = (arg>0) ? fn_args[0] : val_null(); }
                else if (strcmp(vn, "Err") == 0) { res->as.result.ok = false; res->as.result.value = (arg>0) ? fn_args[0] : val_null(); }
                else { res->kind = V_VARIANT; res->as = callee->as; }
                stack_push(&vm->stack, res);
            } else stack_push(&vm->stack, val_null());
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
        case OP_MOD: { Value *r = stack_pop(&vm->stack), *l = stack_pop(&vm->stack); stack_push(&vm->stack, val_number(fmod(to_number(l), to_number(r)))); break; }
        case OP_EQ:  { Value *r = stack_pop(&vm->stack), *l = stack_pop(&vm->stack);
            bool eq = (l->kind == r->kind);
            if (eq && l->kind == V_NUMBER) eq = (l->as.number == r->as.number);
            else if (eq && l->kind == V_MONEY) eq = (l->as.money.amount == r->as.money.amount && strcmp(l->as.money.currency, r->as.money.currency) == 0);
            else if (eq && l->kind == V_STRING) eq = (strcmp(l->as.string, r->as.string) == 0);
            else if (eq && l->kind == V_BOOL) eq = (l->as.boolean == r->as.boolean);
            else if (eq && l->kind == V_VARIANT) eq = (strcmp(l->as.variant.name, r->as.variant.name) == 0);
            else if (eq && l->kind == V_NULL) eq = true;
            stack_push(&vm->stack, val_bool(eq)); break;
        }
        case OP_NEQ: { Value *r = stack_pop(&vm->stack), *l = stack_pop(&vm->stack); stack_push(&vm->stack, val_bool(to_number(l) != to_number(r))); break; }
        case OP_LT:  { Value *r = stack_pop(&vm->stack), *l = stack_pop(&vm->stack); stack_push(&vm->stack, val_bool(to_number(l) < to_number(r))); break; }
        case OP_GT:  { Value *r = stack_pop(&vm->stack), *l = stack_pop(&vm->stack); stack_push(&vm->stack, val_bool(to_number(l) > to_number(r))); break; }
        case OP_LTE: { Value *r = stack_pop(&vm->stack), *l = stack_pop(&vm->stack); stack_push(&vm->stack, val_bool(to_number(l) <= to_number(r))); break; }
        case OP_GTE: { Value *r = stack_pop(&vm->stack), *l = stack_pop(&vm->stack); stack_push(&vm->stack, val_bool(to_number(l) >= to_number(r))); break; }
        case OP_NOT: { Value *v = stack_pop(&vm->stack); stack_push(&vm->stack, val_bool(!is_truthy(v))); break; }
        case OP_AND: { Value *r = stack_pop(&vm->stack), *l = stack_pop(&vm->stack); stack_push(&vm->stack, val_bool(is_truthy(l) && is_truthy(r))); break; }
        case OP_OR:  { Value *r = stack_pop(&vm->stack), *l = stack_pop(&vm->stack); stack_push(&vm->stack, val_bool(is_truthy(l) || is_truthy(r))); break; }
        case OP_NEG: { Value *v = stack_pop(&vm->stack); stack_push(&vm->stack, val_number(-to_number(v))); break; }
        case OP_BUILD_RECORD: {
            Value *rec = val_null(); rec->kind = V_RECORD;
            rec->as.record.count = arg;
            rec->as.record.keys = calloc(arg, sizeof(char*));
            rec->as.record.vals = calloc(arg, sizeof(Value*));
            for (int i = arg - 1; i >= 0; i--) {
                rec->as.record.vals[i] = stack_pop(&vm->stack);
                /* Key is a string constant pushed before the value */
                Value *key_val = stack_pop(&vm->stack);
                rec->as.record.keys[i] = strdup(key_val && key_val->kind == V_STRING ? key_val->as.string : "?");
            }
            stack_push(&vm->stack, rec); break;
        }
        case OP_BUILD_LIST: {
            Value *lst = val_null(); lst->kind = V_LIST;
            lst->as.list.items = calloc(arg, sizeof(Value*));
            lst->as.list.count = arg;
            for (int i = arg - 1; i >= 0; i--) lst->as.list.items[i] = stack_pop(&vm->stack);
            stack_push(&vm->stack, lst); break;
        }
        case OP_GET_INDEX: {
            int idx = (int)to_number(stack_pop(&vm->stack));
            Value *lst = stack_pop(&vm->stack);
            if (lst && lst->kind == V_LIST && idx >= 0 && idx < lst->as.list.count)
                stack_push(&vm->stack, lst->as.list.items[idx]);
            else stack_push(&vm->stack, val_null());
            break;
        }
        case OP_SET_INDEX: {
            Value *val = stack_pop(&vm->stack);
            int idx = (int)to_number(stack_pop(&vm->stack));
            Value *lst = stack_pop(&vm->stack);
            if (lst && lst->kind == V_LIST && idx >= 0 && idx < lst->as.list.count)
                lst->as.list.items[idx] = val;
            stack_push(&vm->stack, lst);
            break;
        }
        case OP_GET_FIELD: {
            Value *rec = stack_pop(&vm->stack);
            const char *field = vm_const(vm, arg)->as.string;
            if (rec && rec->kind == V_RECORD) {
                for (int i = 0; i < rec->as.record.count; i++)
                    if (strcmp(rec->as.record.keys[i], field) == 0)
                        { stack_push(&vm->stack, rec->as.record.vals[i]); break; }
            } else if (rec && rec->kind == V_NUMBER) {
                stack_push(&vm->stack, val_money(rec->as.number, field));
            } else if (rec && rec->kind == V_VARIANT) {
                char buf[128]; snprintf(buf, sizeof(buf), "%s.%s", rec->as.variant.name, field);
                stack_push(&vm->stack, val_variant(buf));
            } else stack_push(&vm->stack, val_null());
            break;
        }
        case OP_RECORD_UPDATE: {
            int count = arg;
            char *fk[32]; Value *fv[32];
            for (int i = count - 1; i >= 0; i--) {
                fv[i] = stack_pop(&vm->stack);
                Value *kv = stack_pop(&vm->stack);
                fk[i] = kv && kv->kind == V_STRING ? strdup(kv->as.string) : strdup("?");
            }
            Value *base = stack_pop(&vm->stack);
            Value *res = val_null(); res->kind = V_RECORD;
            if (base && base->kind == V_RECORD) {
                res->as.record.count = base->as.record.count;
                res->as.record.keys = calloc(base->as.record.count, sizeof(char*));
                res->as.record.vals = calloc(base->as.record.count, sizeof(Value*));
                for (int i = 0; i < base->as.record.count; i++) {
                    res->as.record.keys[i] = strdup(base->as.record.keys[i]);
                    res->as.record.vals[i] = base->as.record.vals[i];
                }
                for (int i = 0; i < count; i++)
                    for (int j = 0; j < res->as.record.count; j++)
                        if (strcmp(res->as.record.keys[j], fk[i]) == 0) { res->as.record.vals[j] = fv[i]; break; }
            }
            stack_push(&vm->stack, res);
            for (int i = 0; i < count; i++) free(fk[i]);
            break;
        }
        case OP_TRY_PROPAGATE: {
            Value *v = stack_pop(&vm->stack);
            if (v && v->kind == V_RESULT) { 
                if (!v->as.result.ok) { fprintf(stderr, "mossvm: Err("); val_print(stderr, v->as.result.value); fprintf(stderr, ")\n"); exit(1); }
                stack_push(&vm->stack, v->as.result.value);
            } else stack_push(&vm->stack, v);
            break;
        }
        case 90: case 91: break; /* TRY/UNWRAP — compile-time, no-op */
        case 100: case 101: break; /* CHECK_EFFECT — compile-time */
        case 110: { /* CALL_PYTHON — push null for now (C VM has no Python C API) */
            for (int i = 0; i < arg; i++) { Value *d = stack_pop(&vm->stack); } /* pop args */
            Value *target = stack_pop(&vm->stack); /* pop target string */
            fprintf(stderr, "mossvm: CALL_PYTHON '%s' not supported in C VM\n",
                    target && target->kind == V_STRING ? target->as.string : "?");
            stack_push(&vm->stack, val_null());
            break;
        }
        case OP_REQUIRE: {
            Value *err_val = stack_pop(&vm->stack);
            fprintf(stderr, "mossvm: require failed: "); val_print(stderr, err_val); fprintf(stderr, "\n"); exit(1);
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
    /* imports — resolve and load imported .mbc files from same directory */
    {
        uint32_t n = read_u32(f);
        char dir[256] = "";
        const char *slash = strrchr(path, '/');
        if (!slash) slash = strrchr(path, '\\');
        if (slash) { memcpy(dir, path, slash - path + 1); dir[slash - path + 1] = 0; }
        for (uint32_t i = 0; i < n; i++) {
            char *imp = read_string(f);
            char *dot = strrchr(imp, '.');
            if (dot) {
                const char *base = strrchr(imp, '/');
                if (!base) base = strrchr(imp, '\\');
                if (base) base++; else base = imp;
                char mbc_path[512];
                snprintf(mbc_path, sizeof(mbc_path), "%s%s", dir, base);
                char *ext = strrchr(mbc_path, '.');
                if (ext) strcpy(ext, ".mbc");
                FILE *impf = fopen(mbc_path, "rb");
                if (impf) {
                    char magic[4]; fread(magic, 1, 4, impf);
                    if (memcmp(magic, "MOSS", 4) == 0) {
                        read_u32(impf); /* version */
                        char *mn = read_string(impf); free(mn);
                        char *sp = read_string(impf); free(sp);
                        int32_t ng = (int32_t)read_u32(impf);
                        for (int32_t j = 0; j < ng; j++) free(read_string(impf));
                        { uint32_t en = read_u32(impf); for (uint32_t j=0;j<en;j++) free(read_string(impf)); }
                        { uint32_t in = read_u32(impf); for (uint32_t j=0;j<in;j++) free(read_string(impf)); }
                        { uint32_t tn = read_u32(impf); for (uint32_t j=0;j<tn;j++) free(read_string(impf)); }
                        char *cn = read_string(impf); free(cn);
                        read_u32(impf); read_u32(impf);
                        { uint8_t d; fread(&d,1,1,impf); }
                        read_u32(impf); read_u32(impf);
                        int32_t ilc = (int32_t)read_u32(impf);
                        for (int32_t j=0;j<ilc;j++) free(read_string(impf));
                        { uint32_t cl=read_u32(impf); char*cb=malloc(cl+1);fread(cb,1,cl,impf);free(cb); }
                        { uint32_t ic=read_u32(impf); for(uint32_t j=0;j<ic;j++){fgetc(impf);for(int k=0;k<5;k++)read_u32(impf);} }
                        int32_t fn = (int32_t)read_u32(impf);
                        for (int32_t j=0;j<fn;j++) {
                            char *fn_name = read_string(impf);
                            int32_t fn_argc = (int32_t)read_u32(impf);
                            read_u32(impf);
                            { uint8_t d; fread(&d,1,1,impf); }
                            read_u32(impf); read_u32(impf);
                            int32_t flc = (int32_t)read_u32(impf);
                            char **fln = calloc(flc,sizeof(char*));
                            for (int32_t k=0;k<flc;k++) fln[k]=read_string(impf);
                            Value **fco=NULL; int32_t fcc=0;
                            { uint32_t cl=read_u32(impf); char*cb=malloc(cl+1);fread(cb,1,cl,impf);cb[cl]=0;
                              for(uint32_t k=0;k<cl;k++)if(cb[k]==',')fcc++; fcc++;
                              fco=calloc(fcc,sizeof(Value*)); int ci=0;
                              char*p=cb; while(*p&&ci<fcc){while(*p==' '||*p=='['||*p==']'||*p==',')p++;
                              if(*p=='"'){p++;char*s=p;while(*p&&*p!='"')p++;*p=0;p++;fco[ci++]=val_string(s);}
                              else if(*p=='-'||(*p>='0'&&*p<='9')){fco[ci++]=val_number(atof(p));while(*p&&*p!=','&&*p!=']')p++;}
                              else if(*p=='n'&&strncmp(p,"null",4)==0){fco[ci++]=val_null();p+=4;}
                              else if(*p=='t'&&strncmp(p,"true",4)==0){fco[ci++]=val_bool(true);p+=4;}
                              else if(*p=='f'&&strncmp(p,"false",5)==0){fco[ci++]=val_bool(false);p+=5;}
                              else p++;} fcc=ci; free(cb); }
                            Instructions fi = read_instructions(impf);
                            vm_register_func(fn_name, fi, fn_argc, flc, fln, fco, fcc);
                            free(fn_name);
                        }
                    }
                    fclose(impf);
                }
            }
            free(imp);
        }
    }
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
    int32_t nfunc = (int32_t)read_u32(f);
    for (int i = 0; i < nfunc; i++) {
        char *fn_name = read_string(f);
        int32_t fn_argc = (int32_t)read_u32(f);
        read_u32(f); /* cap_count */
        { uint8_t dummy; fread(&dummy, 1, 1, f); } /* is_rule */
        read_u32(f); /* source_line */
        read_u32(f); /* source_column */
        int32_t fn_locals = (int32_t)read_u32(f);
        char **fn_local_names = calloc(fn_locals, sizeof(char*));
        for (int j = 0; j < fn_locals; j++) fn_local_names[j] = read_string(f);
        /* Read constants (JSON) */
        int32_t fn_const_count = 0;
        Value **fn_constants = NULL;
        {
            uint32_t cjl = read_u32(f);
            char *cjson = malloc(cjl + 1);
            fread(cjson, 1, cjl, f); cjson[cjl] = 0;
            /* Count and parse */
            for (uint32_t j = 0; j < cjl; j++) if (cjson[j] == ',') fn_const_count++;
            fn_const_count++;
            fn_constants = calloc(fn_const_count, sizeof(Value*));
            int ci = 0;
            char *p = cjson;
            while (*p && ci < fn_const_count) {
                while (*p == ' ' || *p == '[' || *p == ']' || *p == ',') p++;
                if (*p == '"') { p++; char *s = p; while (*p && *p != '"') p++; *p=0; p++; fn_constants[ci++]=val_string(s); }
                else if (*p=='-'||(*p>='0'&&*p<='9')) { fn_constants[ci++]=val_number(atof(p)); while(*p&&*p!=','&&*p!=']')p++; }
                else if (*p=='n'&&strncmp(p,"null",4)==0){fn_constants[ci++]=val_null();p+=4;}
                else if (*p=='t'&&strncmp(p,"true",4)==0){fn_constants[ci++]=val_bool(true);p+=4;}
                else if (*p=='f'&&strncmp(p,"false",5)==0){fn_constants[ci++]=val_bool(false);p+=5;}
                else p++;
            }
            fn_const_count = ci;
            free(cjson);
        }
        Instructions fn_insts = read_instructions(f);
        vm_register_func(fn_name, fn_insts, fn_argc, fn_locals, fn_local_names, fn_constants, fn_const_count);
        free(fn_name);
    }

    fclose(f);
    return true;
}

/* ── Boot builtins ──────────────────────────────────────────────────── */

/* ── Builtin name table (checked before module globals) ──────────────── */
static const char *BUILTIN_NAMES[] = {"print", "len", "assert", "textJoin", "textSplit", "textTrim", "textChars", "textSlice", "textContains", "textIndexOf", "textReplace", "textStartsWith", "textEndsWith", "range", "listNew", "listPush", "listGet", "listSet", "listSlice", "listConcat", "listInsert", "listRemove", "mapNew", "mapPut", "mapGet", "mapHas", "mapKeys", "mapValues", "mapRemove", "jsonParse", "jsonStringify", "readText", "writeText", "fileExists", "listFiles", "httpGet", "httpPostJson", "dbPut", "dbGet", "processRun", "processRunJson", NULL};
#define BUILTIN_COUNT (sizeof(BUILTIN_NAMES)/sizeof(BUILTIN_NAMES[0]) - 1)

static Value *vm_builtin_by_name(const char *name) {
    if (!name) return NULL;
    for (int i = 0; BUILTIN_NAMES[i]; i++)
        if (strcmp(name, BUILTIN_NAMES[i]) == 0) return val_string(name);
    return NULL;
}

/* Look up a builtin by name or fallback index */
static Value *vm_resolve_global(VM *vm, int idx) {
    Value *g = vm_global(vm, idx);
    if (g) return g;
    const char *gn = vm_global_name(vm, idx);
    if (gn) {
        g = vm_builtin_by_name(gn);
        if (g) return g;
        /* Check function registry for imported functions */
        if (vm_find_func(gn) >= 0) return val_string(gn);
        /* Auto-create variants for capitalized names */
        if (*gn >= 'A' && *gn <= 'Z') return val_variant(gn);
    }
    /* No global name registered — use fallback: common builtins at low indices */
    if (idx < (int)BUILTIN_COUNT) return val_string(BUILTIN_NAMES[idx]);
    return NULL;
}

/* ── Main ──────────────────────────────────────────────────────────── */

static void vm_load_module_file(VM *vm, const char *path) {
    vm_load(vm, path);
}

/* Find directory containing mossvm.exe */
static void find_exe_dir(char *buf, size_t len) {
    buf[0] = 0;
#ifdef _WIN32
    GetModuleFileNameA(NULL, buf, (DWORD)len);
    char *slash = strrchr(buf, '\\');
    if (slash) *slash = 0;
#else
    /* Linux: read /proc/self/exe */
    ssize_t n = readlink("/proc/self/exe", buf, len - 1);
    if (n > 0) { buf[n] = 0; char *slash = strrchr(buf, '/'); if (slash) *slash = 0; }
#endif
}

int main(int argc, char *argv[]) {
    if (argc < 2) {
        fprintf(stderr, "Moss VM v0.99 — C VM with embedded selfhost modules\n");
        fprintf(stderr, "usage:\n");
        fprintf(stderr, "  mossvm program.mbc           run bytecode\n");
        fprintf(stderr, "  mossvm --source file.moss     compile via Python + run\n");
        fprintf(stderr, "  mossvm --modules              load embedded .mbc modules + show stats\n");
        return 1;
    }

    /* --modules: load embedded modules from ./moss_modules/ */
    if (strcmp(argv[1], "--modules") == 0) {
        char exe_dir[512];
        find_exe_dir(exe_dir, sizeof(exe_dir));
        fprintf(stderr, "mossvm: loading embedded modules from %s/moss_modules/\n", exe_dir);
        const char *modules[] = {"lexer_core.mbc", "parser_core.mbc", "compiler_core.mbc"};
        for (int i = 0; i < 3; i++) {
            char path[512];
            snprintf(path, sizeof(path), "%s/moss_modules/%s", exe_dir, modules[i]);
            VM mod_vm = {0};
            if (vm_load(&mod_vm, path)) {
                fprintf(stderr, "  loaded %s (%d instructions, %d functions)\n",
                        modules[i], mod_vm.insts.length, func_registry_count);
            } else {
                fprintf(stderr, "  NOT FOUND: %s\n", modules[i]);
            }
        }
        fprintf(stderr, "mossvm: selfhost modules ready (%d functions registered)\n", func_registry_count);
        return 0;
    }

    const char *input = argv[1];
    char temp_mbc[256] = "";
    int used_temp = 0;

    /* --source mode: compile .moss via Python CLI, then run */
    if (argc >= 3 && strcmp(argv[1], "--source") == 0) {
        input = argv[2];
        const char *dot = strrchr(input, '.');
        if (dot && strcmp(dot, ".moss") == 0) {
            snprintf(temp_mbc, sizeof(temp_mbc), "%s.mbc_tmp", input);
            char cmd[1024];
            snprintf(cmd, sizeof(cmd), "python -m mosslang.cli compile \"%s\" -o \"%s\" 2>nul", input, temp_mbc);
            int ret = system(cmd);
            if (ret != 0) {
                snprintf(cmd, sizeof(cmd), "moss compile \"%s\" -o \"%s\" 2>nul", input, temp_mbc);
                ret = system(cmd);
            }
            if (ret == 0) {
                input = temp_mbc;
                used_temp = 1;
            } else {
                fprintf(stderr, "mossvm: cannot compile %s (need Python/moss installed)\n", input);
                return 1;
            }
        }
    }

    VM vm = {0};
    if (!vm_load(&vm, input)) { fprintf(stderr, "LOAD FAILED\n"); fflush(stderr); return 1; }
    fprintf(stderr, "LOAD OK, starting vm_run\n"); fflush(stderr);
    vm_run(&vm);

    if (used_temp) remove(temp_mbc);
    return 0;
}
