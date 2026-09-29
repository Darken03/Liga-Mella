# DESIGN.MD — Liga Mella | Sistema de Diseño Global
> v1.0 prototipo — Solo Django Templates + 1 CSS base + Bootstrap 5.3 CDN. Todo responsive mobile-first.

## 1. Concepto
Liga de Softball barrial/profesional. Estética deportiva MLB: fuerte, contrastada, legible al sol (celular en el play). Pública vibrante, Admin sobria, Capitán intermedia, Anotador ultra-táctil (botones grandes).

## 2. Paleta (variables CSS en `prototipos/css/styles.css`)
```css
--mella-navy: #0A1A3A;   /* header, footer, admin sidebar */
--mella-red: #C81E2E;    /* primario, CTA, marcador */
--mella-red-dark: #9B1220;
--mella-gold: #EAB308;   /* acento, líderes, estrella capitán */
--mella-green: #15803D;  /* campo, victoria */
--mella-field: #1B7A3D;
--mella-dirt: #C68B4E;
--mella-bg: #F4F5F7;     /* fondo app */
--mella-card: #FFFFFF;
--mella-text: #111827;
--mella-muted: #6B7280;
--mella-line: #E5E7EB;
```

## 3. Tipografías
- Titulares: `Oswald, Arial Narrow, sans-serif` (condensada deportiva, uppercase).
- Cuerpo: `Inter, system-ui, sans-serif`.
- Números/marcador: `Oswald 700` tabular.
- Google Fonts vía CDN en prototipos, luego static en Django.

## 4. Layout base (aplica a todo)
- `header.navbar sticky-top`: logo ⚾ LIGA MELLA + nav + botón login. Collapse hamburger <992px.
- `main.container`: max 1200px, padding 16px mobile / 32px desktop.
- `footer`: navy, 3 columnas → 1 columna en móvil.
- Grid: Bootstrap `row > col-12 col-md-6 col-lg-4`. Tablas siempre en `.table-responsive`.
- Breakpoints: 360px (móvil), 768px (tablet), 1024px+ (laptop).

## 5. Componentes (ver `ui-kit.html`)
1. Botones: `.btn-mella` (rojo), `.btn-navy`, `.btn-gold`, `.btn-ghost`. Altura min 44px (táctil).
2. Cards noticia: imagen 16/9, badge torneo, título Oswald, meta fecha.
3. Marcador juego: navy con score rojo/blanco grande, estado EN VIVO parpadeante.
4. Tabla posiciones: 1ro con borde oro, `W-L-PCT-DIF`, fila sticky header.
5. Card equipo: escudo inicial, nombre, récord, botón Ver.
6. Terreno softball (detalle equipo): SVG inline responsive, 10 posiciones: P, C, 1B, 2B, SS, 3B, LF, LCF, RCF, RF + tarjeta Capitán aparte. Click/dot → ficha lateral.
7. Formularios: labels arriba, inputs 44px, focus rojo.
8. Badges: EN VIVO (rojo pulse), FINAL (gris), PRÓXIMO (navy).
9. Sidebar dashboards (admin/capitán/anotador): topbar en móvil, lateral en desktop.

## 6. Las 4 interfaces
| Interfaz | Ruta Django futura | Estilo distinto |
|---|---|---|
| Pública | `/` | Hero + cards, fondo claro |
| Administración | `/admin-liga/` | Sidebar navy, tablas densas, CRUD |
| Capitanes | `/capitan/` | Sidebar + cards roster, convocar |
| Anotador | `/anotador/` | Botones XXL, marcador gigante, modo sol |

## 7. Terreno — especificación
- SVG viewBox 0 0 400 400, outfield verde, infield tierra, bases blancas.
- Coordenadas: P(200,230), C(200,320), 1B(270,230), 2B(230,170), SS(170,170), 3B(130,230), LF(80,110), LCF(150,60), RCF(250,60), RF(320,110).
- Cada jugador = `<g class="player" data-pos>` círculo + dorsal. CSS hover escala. JS vanilla muestra ficha.
- Sin librerías externas, para reutilizar en Django template con `{% for jugador in equipo %}`.

## 8. Responsive checklist
- [ ] Nav colapsa, tablas con scroll-x, terreno escala 100%, botones anotador 100% ancho en móvil.
- [ ] Tablet: 2 columnas cards, sidebar mini.
- [ ] Laptop: 3-4 columnas, sidebar full.

## 9. Pasar a Django (siguiente fase)
- `static/css/styles.css` = copia de prototipo.
- `templates/base_publica.html`, `base_admin.html`, `base_capitan.html`, `base_anotador.html` heredan tokens.
- `templates/ui-kit.html` para validar cambios visuales.
