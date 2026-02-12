
const md = markdownit({html: true})
    .use(texmath, {engine: katex, delimiters: ['dollars', 'brackets']});
for (let divElement of toRender) {
    let textareaElement = divElement.children[0];
    if (textareaElement.tagName == 'TEXTAREA')
        divElement.innerHTML = md.render('\n' + textareaElement.value.trim());
    divElement.style.display = 'inline';
}
