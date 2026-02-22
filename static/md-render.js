
const md = markdownit({html: true})
    .use(texmath, {engine: katex, delimiters: ['dollars', 'brackets']});

function renderElement(element, string, display='inline') {
    element.innerHTML = md.render(string.trim());
    element.style.display = display;
}

function renderElements(toRender) {
    for (let divElement of toRender) {
        let textareaElement = divElement.children[0];
        if (textareaElement.tagName == 'TEXTAREA')
            renderElement(divElement, textareaElement.value);
    }
}
