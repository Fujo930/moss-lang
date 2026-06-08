/* Moss Grove — C platform layer
 *
 * Provides native window management, rendering, input, file watching,
 * clipboard, and process launching for the Moss-native editor.
 *
 * This is a stub API surface. Full implementation planned for v0.25+
 * in the moss-grove repository.
 *
 * Build: cc -c grove.c -o grove.o
 * Link:  cc grove.o -lSDL2 -lGLEW -o moss-grove
 */

#ifndef GROVE_H
#define GROVE_H

#include <stdint.h>
#include <stdbool.h>

/* ── Window ──────────────────────────────────────────────── */
typedef struct GroveWindow GroveWindow;
GroveWindow *grove_window_open(const char *title, int w, int h);
void         grove_window_close(GroveWindow *win);
void         grove_window_poll_events(GroveWindow *win);
bool         grove_window_should_close(GroveWindow *win);
void         grove_window_swap_buffers(GroveWindow *win);

/* ── Rendering ──────────────────────────────────────────── */
void grove_clear(float r, float g, float b, float a);
void grove_draw_rect(float x, float y, float w, float h, uint32_t color);
void grove_draw_text(const char *text, float x, float y, float size, uint32_t color);
void grove_draw_line(float x1, float y1, float x2, float y2, uint32_t color, float width);

/* ── Input ───────────────────────────────────────────────── */
typedef enum { GK_NONE, GK_CHAR, GK_ENTER, GK_TAB, GK_ESC, GK_BACKSPACE,
               GK_DELETE, GK_LEFT, GK_RIGHT, GK_UP, GK_DOWN,
               GK_HOME, GK_END, GK_PAGEUP, GK_PAGEDOWN } GroveKey;

typedef struct { GroveKey key; uint32_t codepoint; bool ctrl, alt, shift; } GroveEvent;
GroveEvent grove_next_event(void);

/* ── System ──────────────────────────────────────────────── */
char *grove_clipboard_get(void);
void  grove_clipboard_set(const char *text);
bool  grove_file_watch(const char *path, void (*callback)(const char *));
int   grove_process_run(const char **argv, char **stdout_buf, char **stderr_buf);
#endif
