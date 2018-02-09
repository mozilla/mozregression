# Testing documentation

First install [bundler](https://bundler.io/) for ruby:

```
gem install bundler
```

Then install [jekyll](https://jekyllrb.com/docs/usage/) adapted to github:

```
bundle install --path vendor/bundle --binstubs
```

You can test your changes with:

```
bin/jekyll serve --baseurl ''
```

Note that **nodejs** may need to be installed on your system to run **jekyll**.
