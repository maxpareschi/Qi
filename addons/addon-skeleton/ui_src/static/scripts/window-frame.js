localStorage.getItem("_x_darkMode_on") === "true" &&
  document.documentElement.classList.add("dark");

const match_resizer = document.querySelectorAll(".pywebview-resizer");
const match_minimize = document.querySelectorAll(".pywebview-minimize");
const match_maximize = document.querySelectorAll(".pywebview-maximize");
const match_close = document.querySelectorAll(".pywebview-close");

match_resizer.forEach((resizer) => {
  resizer.onmousedown = () => {
    pywebview.api.start_resize();
  };
  resizer.onmouseup = () => {
    pywebview.api.stop_resize();
  };
});

match_minimize.forEach((minimize) => {
  minimize.onclick = () => {
    pywebview.api.minimize_window();
  };
});

match_maximize.forEach((maximize) => {
  maximize.onclick = () => {
    pywebview.api.maximize_window();
  };
});

match_close.forEach((close) => {
  close.onclick = () => {
    pywebview.api.close_window();
  };
});
