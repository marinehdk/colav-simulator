document.querySelectorAll('[data-reveal]').forEach(button => {
  button.addEventListener('click', () => {
    const expanded = button.getAttribute('aria-expanded') === 'true';
    button.setAttribute('aria-expanded', String(!expanded));
  });
});

document.querySelectorAll('[data-quiz]').forEach(quiz => {
  const feedback = quiz.querySelector('.feedback');
  quiz.querySelectorAll('button[data-answer]').forEach(button => {
    button.addEventListener('click', () => {
      const correct = button.dataset.answer === quiz.dataset.correct;
      feedback.textContent = correct ? quiz.dataset.success : quiz.dataset.retry;
      feedback.className = `feedback ${correct ? 'good' : 'bad'}`;
    });
  });
});
