// Fast C++ rules engine for Hanat, exposed to Python via the CPython C-API.
//
// This is a line-for-line port of the pure-Python reference engine in
// hanat/_pyboard.py: identical pseudo-legal generation, the same
// make-move/king-attacked legality filter, the same SAN and FEN handling. The
// perft suite and a backend-parity test pin the two implementations together.
//
// No third-party build dependency -- just a C++17 compiler and the CPython
// headers. Built in place to hanat/_chess<EXT_SUFFIX>.so by setup.py.

#define PY_SSIZE_T_CLEAN
#include <Python.h>

#include <array>
#include <cctype>
#include <cstdlib>
#include <string>
#include <vector>

namespace {

const int KNIGHT[8][2] = {{1, 2}, {2, 1}, {2, -1}, {1, -2},
                          {-1, -2}, {-2, -1}, {-2, 1}, {-1, 2}};
const int KING[8][2] = {{-1, -1}, {-1, 0}, {-1, 1}, {0, -1},
                        {0, 1}, {1, -1}, {1, 0}, {1, 1}};
const int BISHOP[4][2] = {{1, 1}, {1, -1}, {-1, 1}, {-1, -1}};
const int ROOK[4][2] = {{1, 0}, {-1, 0}, {0, 1}, {0, -1}};

inline int file_of(int sq) { return sq & 7; }
inline int rank_of(int sq) { return sq >> 3; }
inline int sq_of(int f, int r) { return r * 8 + f; }
inline bool on_board(int f, int r) { return f >= 0 && f < 8 && r >= 0 && r < 8; }
inline bool is_white(char p) { return p >= 'A' && p <= 'Z'; }
inline char color_of(char p) { return is_white(p) ? 'w' : 'b'; }
inline char lc(char c) { return (char)std::tolower((unsigned char)c); }
inline char uc(char c) { return (char)std::toupper((unsigned char)c); }

inline std::string sq_name(int sq) {
    std::string s;
    s += (char)('a' + file_of(sq));
    s += (char)('1' + rank_of(sq));
    return s;
}

struct Move {
    int from;
    int to;
    char promo;  // 0 or lowercase q/r/b/n
};

struct Board {
    char sq[64];
    char turn;       // 'w' or 'b'
    bool cK, cQ, ck, cq;
    int ep;          // -1 = none
    int halfmove;
    int fullmove;

    void clear() {
        for (int i = 0; i < 64; i++) sq[i] = 0;
        turn = 'w';
        cK = cQ = ck = cq = false;
        ep = -1;
        halfmove = 0;
        fullmove = 1;
    }

    char opp() const { return turn == 'w' ? 'b' : 'w'; }

    // ---- FEN -------------------------------------------------------- //
    bool set_fen(const std::string& fen) {
        // split on whitespace
        std::vector<std::string> parts;
        std::string cur;
        for (char c : fen) {
            if (c == ' ' || c == '\t' || c == '\n') {
                if (!cur.empty()) { parts.push_back(cur); cur.clear(); }
            } else {
                cur += c;
            }
        }
        if (!cur.empty()) parts.push_back(cur);
        if (parts.size() < 4) return false;

        for (int i = 0; i < 64; i++) sq[i] = 0;
        int rank = 7, file = 0;
        for (char c : parts[0]) {
            if (c == '/') { rank -= 1; file = 0; }
            else if (c >= '1' && c <= '8') { file += c - '0'; }
            else {
                char l = lc(c);
                if (l != 'p' && l != 'n' && l != 'b' && l != 'r' && l != 'q' && l != 'k')
                    return false;
                if (rank < 0 || rank > 7 || file < 0 || file > 7) return false;
                sq[sq_of(file, rank)] = c;
                file += 1;
            }
        }
        turn = (parts[1] == "w") ? 'w' : 'b';
        cK = cQ = ck = cq = false;
        for (char c : parts[2]) {
            if (c == 'K') cK = true;
            else if (c == 'Q') cQ = true;
            else if (c == 'k') ck = true;
            else if (c == 'q') cq = true;
        }
        if (parts[3] == "-") {
            ep = -1;
        } else {
            if (parts[3].size() != 2) return false;
            int f = parts[3][0] - 'a';
            int r = parts[3][1] - '1';
            if (!on_board(f, r)) return false;
            ep = sq_of(f, r);
        }
        halfmove = (parts.size() > 4) ? std::atoi(parts[4].c_str()) : 0;
        fullmove = (parts.size() > 5) ? std::atoi(parts[5].c_str()) : 1;
        return true;
    }

    std::string fen() const {
        std::string out;
        for (int rank = 7; rank >= 0; rank--) {
            int empty = 0;
            for (int file = 0; file < 8; file++) {
                char p = sq[sq_of(file, rank)];
                if (p == 0) { empty++; }
                else {
                    if (empty) { out += std::to_string(empty); empty = 0; }
                    out += p;
                }
            }
            if (empty) out += std::to_string(empty);
            if (rank) out += '/';
        }
        out += ' ';
        out += (turn == 'w') ? 'w' : 'b';
        out += ' ';
        std::string cast;
        if (cK) cast += 'K';
        if (cQ) cast += 'Q';
        if (ck) cast += 'k';
        if (cq) cast += 'q';
        out += cast.empty() ? "-" : cast;
        out += ' ';
        out += (ep < 0) ? "-" : sq_name(ep);
        out += ' ';
        out += std::to_string(halfmove);
        out += ' ';
        out += std::to_string(fullmove);
        return out;
    }

    // ---- queries ---------------------------------------------------- //
    int king_square(char color) const {
        char k = (color == 'w') ? 'K' : 'k';
        for (int s = 0; s < 64; s++)
            if (sq[s] == k) return s;
        return -1;
    }

    bool is_attacked(int s, char by) const {
        int f = file_of(s), r = rank_of(s);
        if (by == 'w') {
            for (int df = -1; df <= 1; df += 2) {
                int nf = f + df, nr = r - 1;
                if (on_board(nf, nr) && sq[sq_of(nf, nr)] == 'P') return true;
            }
        } else {
            for (int df = -1; df <= 1; df += 2) {
                int nf = f + df, nr = r + 1;
                if (on_board(nf, nr) && sq[sq_of(nf, nr)] == 'p') return true;
            }
        }
        char knight = (by == 'w') ? 'N' : 'n';
        for (auto& d : KNIGHT) {
            int nf = f + d[0], nr = r + d[1];
            if (on_board(nf, nr) && sq[sq_of(nf, nr)] == knight) return true;
        }
        char king = (by == 'w') ? 'K' : 'k';
        for (auto& d : KING) {
            int nf = f + d[0], nr = r + d[1];
            if (on_board(nf, nr) && sq[sq_of(nf, nr)] == king) return true;
        }
        char bishop = (by == 'w') ? 'B' : 'b';
        char rook = (by == 'w') ? 'R' : 'r';
        char queen = (by == 'w') ? 'Q' : 'q';
        for (auto& d : BISHOP) {
            int nf = f + d[0], nr = r + d[1];
            while (on_board(nf, nr)) {
                char p = sq[sq_of(nf, nr)];
                if (p != 0) { if (p == bishop || p == queen) return true; break; }
                nf += d[0]; nr += d[1];
            }
        }
        for (auto& d : ROOK) {
            int nf = f + d[0], nr = r + d[1];
            while (on_board(nf, nr)) {
                char p = sq[sq_of(nf, nr)];
                if (p != 0) { if (p == rook || p == queen) return true; break; }
                nf += d[0]; nr += d[1];
            }
        }
        return false;
    }

    bool is_check() const { return is_attacked(king_square(turn), turn == 'w' ? 'b' : 'w'); }

    // ---- pseudo-legal generation ------------------------------------ //
    void gen_step(int s, char color, const int dirs[][2], int n, std::vector<Move>& mv) const {
        int f = file_of(s), r = rank_of(s);
        for (int i = 0; i < n; i++) {
            int nf = f + dirs[i][0], nr = r + dirs[i][1];
            if (!on_board(nf, nr)) continue;
            int t = sq_of(nf, nr);
            char occ = sq[t];
            if (occ == 0 || color_of(occ) != color) mv.push_back({s, t, 0});
        }
    }

    void gen_slide(int s, char color, const int dirs[][2], int n, std::vector<Move>& mv) const {
        int f = file_of(s), r = rank_of(s);
        for (int i = 0; i < n; i++) {
            int nf = f + dirs[i][0], nr = r + dirs[i][1];
            while (on_board(nf, nr)) {
                int t = sq_of(nf, nr);
                char occ = sq[t];
                if (occ == 0) { mv.push_back({s, t, 0}); }
                else { if (color_of(occ) != color) mv.push_back({s, t, 0}); break; }
                nf += dirs[i][0]; nr += dirs[i][1];
            }
        }
    }

    void add_pawn(int from, int to, int to_rank, int promo_rank, std::vector<Move>& mv) const {
        if (to_rank == promo_rank) {
            const char promos[4] = {'q', 'r', 'b', 'n'};
            for (char p : promos) mv.push_back({from, to, p});
        } else {
            mv.push_back({from, to, 0});
        }
    }

    void gen_pawn(int s, char color, std::vector<Move>& mv) const {
        int f = file_of(s), r = rank_of(s);
        int forward = (color == 'w') ? 1 : -1;
        int start_rank = (color == 'w') ? 1 : 6;
        int promo_rank = (color == 'w') ? 7 : 0;
        int one = sq_of(f, r + forward);
        if (sq[one] == 0) {
            add_pawn(s, one, r + forward, promo_rank, mv);
            if (r == start_rank) {
                int two = sq_of(f, r + 2 * forward);
                if (sq[two] == 0) mv.push_back({s, two, 0});
            }
        }
        for (int df = -1; df <= 1; df += 2) {
            int nf = f + df, nr = r + forward;
            if (!on_board(nf, nr)) continue;
            int t = sq_of(nf, nr);
            char occ = sq[t];
            if (occ != 0 && color_of(occ) != color) add_pawn(s, t, nr, promo_rank, mv);
            else if (t == ep) mv.push_back({s, t, 0});
        }
    }

    void gen_castling(int s, char color, std::vector<Move>& mv) const {
        char enemy = (color == 'w') ? 'b' : 'w';
        if (is_attacked(s, enemy)) return;
        if (color == 'w') {
            if (cK && sq[5] == 0 && sq[6] == 0 && !is_attacked(5, enemy) &&
                !is_attacked(6, enemy) && sq[7] == 'R')
                mv.push_back({4, 6, 0});
            if (cQ && sq[3] == 0 && sq[2] == 0 && sq[1] == 0 && !is_attacked(3, enemy) &&
                !is_attacked(2, enemy) && sq[0] == 'R')
                mv.push_back({4, 2, 0});
        } else {
            if (ck && sq[61] == 0 && sq[62] == 0 && !is_attacked(61, enemy) &&
                !is_attacked(62, enemy) && sq[63] == 'r')
                mv.push_back({60, 62, 0});
            if (cq && sq[59] == 0 && sq[58] == 0 && sq[57] == 0 && !is_attacked(59, enemy) &&
                !is_attacked(58, enemy) && sq[56] == 'r')
                mv.push_back({60, 58, 0});
        }
    }

    void pseudo_legal(std::vector<Move>& mv) const {
        char color = turn;
        for (int s = 0; s < 64; s++) {
            char piece = sq[s];
            if (piece == 0 || color_of(piece) != color) continue;
            char kind = lc(piece);
            switch (kind) {
                case 'p': gen_pawn(s, color, mv); break;
                case 'n': gen_step(s, color, KNIGHT, 8, mv); break;
                case 'k': gen_step(s, color, KING, 8, mv); gen_castling(s, color, mv); break;
                case 'b': gen_slide(s, color, BISHOP, 4, mv); break;
                case 'r': gen_slide(s, color, ROOK, 4, mv); break;
                case 'q': gen_slide(s, color, BISHOP, 4, mv); gen_slide(s, color, ROOK, 4, mv); break;
            }
        }
    }

    void touch_rook(int s) {
        if (s == 0) cQ = false;
        else if (s == 7) cK = false;
        else if (s == 56) cq = false;
        else if (s == 63) ck = false;
    }

    void apply(const Move& m) {
        char piece = sq[m.from];
        char color = color_of(piece);
        char kind = lc(piece);
        char captured = sq[m.to];
        int prev_ep = ep;

        sq[m.to] = piece;
        sq[m.from] = 0;
        bool is_capture = captured != 0;

        if (kind == 'p' && m.to == prev_ep) {
            int cap = (color == 'w') ? m.to - 8 : m.to + 8;
            sq[cap] = 0;
            is_capture = true;
        }
        if (m.promo) {
            sq[m.to] = (color == 'w') ? uc(m.promo) : m.promo;
        }
        if (kind == 'k' && std::abs(file_of(m.to) - file_of(m.from)) == 2) {
            if (m.to == 6) { sq[5] = sq[7]; sq[7] = 0; }
            else if (m.to == 2) { sq[3] = sq[0]; sq[0] = 0; }
            else if (m.to == 62) { sq[61] = sq[63]; sq[63] = 0; }
            else if (m.to == 58) { sq[59] = sq[56]; sq[56] = 0; }
        }
        if (kind == 'k') {
            if (color == 'w') { cK = cQ = false; }
            else { ck = cq = false; }
        }
        touch_rook(m.from);
        touch_rook(m.to);

        if (kind == 'p' && std::abs(m.to - m.from) == 16)
            ep = (m.from + m.to) / 2;
        else
            ep = -1;

        if (kind == 'p' || is_capture) halfmove = 0;
        else halfmove += 1;

        if (color == 'b') fullmove += 1;
        turn = (color == 'w') ? 'b' : 'w';
    }

    void legal_moves(std::vector<Move>& out) const {
        char color = turn;
        char enemy = (color == 'w') ? 'b' : 'w';
        std::vector<Move> pseudo;
        pseudo.reserve(64);
        pseudo_legal(pseudo);
        for (const Move& m : pseudo) {
            Board trial = *this;
            trial.apply(m);
            if (!trial.is_attacked(trial.king_square(color), enemy))
                out.push_back(m);
        }
    }

    bool is_legal(const Move& m) const {
        std::vector<Move> legal;
        legal_moves(legal);
        for (const Move& o : legal)
            if (o.from == m.from && o.to == m.to && o.promo == m.promo) return true;
        return false;
    }

    bool is_checkmate() const {
        if (!is_check()) return false;
        std::vector<Move> legal; legal_moves(legal);
        return legal.empty();
    }
    bool is_stalemate() const {
        if (is_check()) return false;
        std::vector<Move> legal; legal_moves(legal);
        return legal.empty();
    }

    bool is_insufficient() const {
        int bishops_light = 0, bishops_dark = 0, knights = 0;
        for (int s = 0; s < 64; s++) {
            char p = sq[s];
            if (p == 0) continue;
            char kind = lc(p);
            if (kind == 'p' || kind == 'r' || kind == 'q') return false;
            if (kind == 'n') knights++;
            else if (kind == 'b') {
                if ((file_of(s) + rank_of(s)) % 2 == 0) bishops_dark++;
                else bishops_light++;
            }
        }
        int minors = knights + bishops_light + bishops_dark;
        if (minors <= 1) return true;
        if (knights == 0 && (bishops_light == 0 || bishops_dark == 0)) return true;
        return false;
    }

    // ---- SAN -------------------------------------------------------- //
    std::string check_suffix(const Move& m) const {
        Board trial = *this;
        trial.apply(m);
        if (trial.is_check()) {
            std::vector<Move> legal; trial.legal_moves(legal);
            return legal.empty() ? "#" : "+";
        }
        return "";
    }

    std::string disambiguation(const Move& m) const {
        char piece = sq[m.from];
        char kind = lc(piece);
        std::vector<int> rivals;
        std::vector<Move> legal; legal_moves(legal);
        for (const Move& o : legal) {
            if (o.to != m.to || o.from == m.from) continue;
            char op = sq[o.from];
            if (op != 0 && lc(op) == kind && op == piece) rivals.push_back(o.from);
        }
        if (rivals.empty()) return "";
        bool same_file = false, same_rank = false;
        for (int s : rivals) {
            if (file_of(s) == file_of(m.from)) same_file = true;
            if (rank_of(s) == rank_of(m.from)) same_rank = true;
        }
        std::string name = sq_name(m.from);
        if (!same_file) return name.substr(0, 1);
        if (!same_rank) return name.substr(1, 1);
        return name;
    }

    std::string san(const Move& m) const {
        char piece = sq[m.from];
        char kind = lc(piece);
        if (kind == 'k' && std::abs(file_of(m.to) - file_of(m.from)) == 2) {
            std::string t = (file_of(m.to) == 6) ? "O-O" : "O-O-O";
            return t + check_suffix(m);
        }
        bool is_capture = sq[m.to] != 0 || (kind == 'p' && m.to == ep);
        std::string text;
        if (kind == 'p') {
            if (is_capture) { text += sq_name(m.from)[0]; text += 'x'; }
            text += sq_name(m.to);
            if (m.promo) { text += '='; text += uc(m.promo); }
        } else {
            text += uc(piece);
            text += disambiguation(m);
            if (is_capture) text += 'x';
            text += sq_name(m.to);
        }
        return text + check_suffix(m);
    }

    bool parse_san(const std::string& raw, Move& out) const {
        std::string cleaned;
        // trim whitespace, drop ! and ?, then strip trailing + and #
        size_t a = raw.find_first_not_of(" \t\n");
        size_t b = raw.find_last_not_of(" \t\n");
        if (a != std::string::npos)
            for (size_t i = a; i <= b; i++) {
                char c = raw[i];
                if (c != '!' && c != '?') cleaned += c;
            }
        while (!cleaned.empty() && (cleaned.back() == '+' || cleaned.back() == '#'))
            cleaned.pop_back();

        std::vector<Move> legal; legal_moves(legal);
        for (const Move& m : legal) {
            std::string s = san(m);
            while (!s.empty() && (s.back() == '+' || s.back() == '#')) s.pop_back();
            if (s == cleaned) { out = m; return true; }
        }
        return false;
    }

    long perft(int depth) const {
        if (depth == 0) return 1;
        std::vector<Move> legal; legal_moves(legal);
        if (depth == 1) return (long)legal.size();
        long total = 0;
        for (const Move& m : legal) {
            Board child = *this;
            child.apply(m);
            total += child.perft(depth - 1);
        }
        return total;
    }
};

const char START_FEN[] = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1";

// ====================================================================== //
// CPython wrapper type: hanat._chess.Board
// ====================================================================== //

struct BoardObject {
    PyObject_HEAD
    Board board;
};

static PyTypeObject BoardType;

static PyObject* make_board() {
    BoardObject* self = (BoardObject*)BoardType.tp_alloc(&BoardType, 0);
    if (self) self->board.clear();
    return (PyObject*)self;
}

static PyObject* Board_new(PyTypeObject* type, PyObject*, PyObject*) {
    BoardObject* self = (BoardObject*)type->tp_alloc(type, 0);
    if (self) self->board.clear();
    return (PyObject*)self;
}

static int Board_init(PyObject* self, PyObject* args, PyObject*) {
    const char* fen = START_FEN;
    if (!PyArg_ParseTuple(args, "|s", &fen)) return -1;
    if (!((BoardObject*)self)->board.set_fen(fen)) {
        PyErr_Format(PyExc_ValueError, "invalid FEN: %s", fen);
        return -1;
    }
    return 0;
}

static void Board_dealloc(PyObject* self) { Py_TYPE(self)->tp_free(self); }

static Board& B(PyObject* self) { return ((BoardObject*)self)->board; }

static PyObject* Board_fen(PyObject* self, PyObject*) {
    return PyUnicode_FromString(B(self).fen().c_str());
}

static PyObject* Board_set_fen(PyObject* self, PyObject* args) {
    const char* fen;
    if (!PyArg_ParseTuple(args, "s", &fen)) return NULL;
    if (!B(self).set_fen(fen)) {
        PyErr_Format(PyExc_ValueError, "invalid FEN: %s", fen);
        return NULL;
    }
    Py_RETURN_NONE;
}

static PyObject* Board_copy(PyObject* self, PyObject*) {
    PyObject* n = make_board();
    if (!n) return NULL;
    B(n) = B(self);
    return n;
}

static PyObject* Board_piece_at(PyObject* self, PyObject* args) {
    int s;
    if (!PyArg_ParseTuple(args, "i", &s)) return NULL;
    if (s < 0 || s > 63) { PyErr_SetString(PyExc_IndexError, "square out of range"); return NULL; }
    char c = B(self).sq[s];
    if (c == 0) Py_RETURN_NONE;
    char buf[2] = {c, 0};
    return PyUnicode_FromString(buf);
}

static PyObject* Board_king_square(PyObject* self, PyObject* args) {
    const char* color;
    if (!PyArg_ParseTuple(args, "s", &color)) return NULL;
    return PyLong_FromLong(B(self).king_square(color[0]));
}

static PyObject* Board_is_attacked(PyObject* self, PyObject* args) {
    int s; const char* by;
    if (!PyArg_ParseTuple(args, "is", &s, &by)) return NULL;
    return PyBool_FromLong(B(self).is_attacked(s, by[0]));
}

static PyObject* Board_is_check(PyObject* self, PyObject*) { return PyBool_FromLong(B(self).is_check()); }
static PyObject* Board_is_checkmate(PyObject* self, PyObject*) { return PyBool_FromLong(B(self).is_checkmate()); }
static PyObject* Board_is_stalemate(PyObject* self, PyObject*) { return PyBool_FromLong(B(self).is_stalemate()); }
static PyObject* Board_is_insufficient(PyObject* self, PyObject*) { return PyBool_FromLong(B(self).is_insufficient()); }

static PyObject* move_tuple(const Move& m) {
    char buf[2] = {m.promo, 0};
    return Py_BuildValue("iis", m.from, m.to, m.promo ? buf : "");
}

static PyObject* Board_legal_moves(PyObject* self, PyObject*) {
    std::vector<Move> legal;
    B(self).legal_moves(legal);
    PyObject* list = PyList_New(legal.size());
    if (!list) return NULL;
    for (size_t i = 0; i < legal.size(); i++) {
        PyObject* t = move_tuple(legal[i]);
        if (!t) { Py_DECREF(list); return NULL; }
        PyList_SET_ITEM(list, i, t);
    }
    return list;
}

static bool parse_move_args(PyObject* args, Move& m) {
    int from, to;
    const char* promo = "";
    if (!PyArg_ParseTuple(args, "ii|s", &from, &to, &promo)) return false;
    m.from = from;
    m.to = to;
    m.promo = (promo && promo[0]) ? lc(promo[0]) : 0;
    return true;
}

static PyObject* Board_apply(PyObject* self, PyObject* args) {
    Move m;
    if (!parse_move_args(args, m)) return NULL;
    B(self).apply(m);
    Py_RETURN_NONE;
}

static PyObject* Board_push(PyObject* self, PyObject* args) {
    Move m;
    if (!parse_move_args(args, m)) return NULL;
    if (!B(self).is_legal(m)) {
        PyErr_Format(PyExc_ValueError, "illegal move: %s%s in %s",
                     sq_name(m.from).c_str(), sq_name(m.to).c_str(), B(self).fen().c_str());
        return NULL;
    }
    B(self).apply(m);
    Py_RETURN_NONE;
}

static PyObject* Board_san(PyObject* self, PyObject* args) {
    Move m;
    if (!parse_move_args(args, m)) return NULL;
    return PyUnicode_FromString(B(self).san(m).c_str());
}

static PyObject* Board_parse_san(PyObject* self, PyObject* args) {
    const char* text;
    if (!PyArg_ParseTuple(args, "s", &text)) return NULL;
    Move m;
    if (!B(self).parse_san(text, m)) {
        PyErr_Format(PyExc_ValueError, "illegal or ambiguous SAN: %s in %s",
                     text, B(self).fen().c_str());
        return NULL;
    }
    return move_tuple(m);
}

static PyObject* Board_perft(PyObject* self, PyObject* args) {
    int depth;
    if (!PyArg_ParseTuple(args, "i", &depth)) return NULL;
    long n;
    Py_BEGIN_ALLOW_THREADS
    n = B(self).perft(depth);
    Py_END_ALLOW_THREADS
    return PyLong_FromLong(n);
}

static PyMethodDef Board_methods[] = {
    {"fen", Board_fen, METH_NOARGS, "Serialise to FEN."},
    {"set_fen", Board_set_fen, METH_VARARGS, "Load from FEN."},
    {"copy", Board_copy, METH_NOARGS, "Independent copy."},
    {"piece_at", Board_piece_at, METH_VARARGS, "Piece char at a square, or None."},
    {"king_square", Board_king_square, METH_VARARGS, "Square of a colour's king."},
    {"is_attacked", Board_is_attacked, METH_VARARGS, "Is a square attacked by a colour?"},
    {"is_check", Board_is_check, METH_NOARGS, ""},
    {"is_checkmate", Board_is_checkmate, METH_NOARGS, ""},
    {"is_stalemate", Board_is_stalemate, METH_NOARGS, ""},
    {"is_insufficient_material", Board_is_insufficient, METH_NOARGS, ""},
    {"legal_moves", Board_legal_moves, METH_NOARGS, "List of (from, to, promo) tuples."},
    {"apply", Board_apply, METH_VARARGS, "Apply a move (no legality check)."},
    {"push", Board_push, METH_VARARGS, "Apply a legal move (validated)."},
    {"san", Board_san, METH_VARARGS, "SAN for a move."},
    {"parse_san", Board_parse_san, METH_VARARGS, "Parse SAN into (from, to, promo)."},
    {"perft", Board_perft, METH_VARARGS, "Count legal-move-tree leaves to depth."},
    {NULL, NULL, 0, NULL},
};

static PyObject* Board_get_turn(PyObject* self, void*) {
    return PyUnicode_FromString(B(self).turn == 'w' ? "w" : "b");
}
static PyObject* Board_get_halfmove(PyObject* self, void*) { return PyLong_FromLong(B(self).halfmove); }
static PyObject* Board_get_fullmove(PyObject* self, void*) { return PyLong_FromLong(B(self).fullmove); }
static PyObject* Board_get_ep(PyObject* self, void*) {
    int e = B(self).ep;
    if (e < 0) Py_RETURN_NONE;
    return PyLong_FromLong(e);
}

static PyGetSetDef Board_getset[] = {
    {"turn", Board_get_turn, NULL, "Side to move: 'w' or 'b'.", NULL},
    {"halfmove_clock", Board_get_halfmove, NULL, "Halfmove clock.", NULL},
    {"fullmove_number", Board_get_fullmove, NULL, "Fullmove number.", NULL},
    {"ep_square", Board_get_ep, NULL, "En passant target square or None.", NULL},
    {NULL, NULL, NULL, NULL, NULL},
};

static PyModuleDef chessmodule = {
    PyModuleDef_HEAD_INIT, "_chess", "Fast C++ chess rules engine.", -1, NULL,
    NULL, NULL, NULL, NULL,
};

}  // namespace

PyMODINIT_FUNC PyInit__chess(void) {
    BoardType = {PyVarObject_HEAD_INIT(NULL, 0)};
    BoardType.tp_name = "hanat._chess.Board";
    BoardType.tp_basicsize = sizeof(BoardObject);
    BoardType.tp_itemsize = 0;
    BoardType.tp_flags = Py_TPFLAGS_DEFAULT;
    BoardType.tp_doc = "A chess position (C++ backed).";
    BoardType.tp_new = Board_new;
    BoardType.tp_init = Board_init;
    BoardType.tp_dealloc = Board_dealloc;
    BoardType.tp_methods = Board_methods;
    BoardType.tp_getset = Board_getset;
    if (PyType_Ready(&BoardType) < 0) return NULL;

    PyObject* m = PyModule_Create(&chessmodule);
    if (!m) return NULL;
    Py_INCREF(&BoardType);
    if (PyModule_AddObject(m, "Board", (PyObject*)&BoardType) < 0) {
        Py_DECREF(&BoardType);
        Py_DECREF(m);
        return NULL;
    }
    return m;
}
