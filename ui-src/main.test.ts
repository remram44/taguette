import {greet} from './main';

test('greeting', () => {
  expect(greet('Foo')).toBe('Hello Foo')
});
