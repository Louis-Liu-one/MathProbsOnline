
const md = markdownit({html: true})
    .use(texmath, {engine: katex, delimiters: ['dollars', 'brackets']});
bodydiv.innerHTML = md.render(bodytext.value);
bodydiv.style.display = 'inline';
