
bodydiv.innerHTML = marked.parse(bodytext.value);
renderMathInElement(bodydiv, {
    delimiters: [
        {left: '$$', right: '$$', display: true},
        {left: '\\[', right: '\\]', display: true},
        {left: '$', right: '$', display: false},
        {left: '\\(', right: '\\)', display: false},
    ],
});
