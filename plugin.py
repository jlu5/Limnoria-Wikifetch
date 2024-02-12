###
# Copyright (c) 2024, James Lu
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
#   * Redistributions of source code must retain the above copyright notice,
#     this list of conditions, and the following disclaimer.
#   * Redistributions in binary form must reproduce the above copyright notice,
#     this list of conditions, and the following disclaimer in the
#     documentation and/or other materials provided with the distribution.
#   * Neither the name of the author of this software nor the name of
#     contributors to this software may be used to endorse or promote products
#     derived from this software without specific prior written consent.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED.  IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.

###
import asyncio
import functools
import re

import mwparserfromhell
import pywikifetch

from supybot.commands import callbacks, getopts, wrap
from supybot.i18n import PluginInternationalization

_ = PluginInternationalization('Wikifetch')

class WikiIRCFormatter(pywikifetch.wikitext_formatter.PlainTextFormatter):
    @functools.singledispatchmethod
    def format_node(self, node):
        yield from super().format_node(node)

    @format_node.register
    def format_tag(self, node: mwparserfromhell.nodes.tag.Tag):
        if node.tag == 'b':
            yield '\x02'
            yield from self.format_node(node.contents)
            yield '\x02'
        elif node.tag == 'i':
            yield '\x1d'
            yield from self.format_node(node.contents)
            yield '\x1d'
        else:
            yield from super().format_tag(node)

class Wikifetch(callbacks.Plugin):
    """Fetch content from MediaWiki-powered wikis"""
    threaded = True

    @staticmethod
    def _text_cleanup(s):
        # Remove parentheses with no text inside, usually left behind due to missing templates
        return re.sub(r' [([]\W*?[)\]]', '', s)

    async def _fetch_wiki(self, irc, site, query, use_markdown=False, first_line_only=False):
        formatter_class = pywikifetch.MarkdownFormatter if use_markdown else WikiIRCFormatter
        async with pywikifetch.Wiki(site, formatter_class=formatter_class) as wiki:
            search_results = await wiki.search(query)
            self.log.debug("Wikifetch search results for %s:", ', '.join(search_results))
            full_text, url = await wiki.fetch(search_results[0], summary=True)

            full_text = self._text_cleanup(full_text)
            # Note: not using splitlines() as that splits on IRC italics too
            lines = list(filter(None, full_text.split('\n')))

            url_pretty = format(' %u', url)
            self.log.debug("Wikifetch formatted lines: %r", lines)
            if first_line_only:
                text = lines[0] + url_pretty
                irc.reply(text)
            else:
                lines = list(lines)
                lines[-1] += url_pretty
                irc.replies(lines, oneToOne=False)

    def _wiki(self, irc, msg, site, query):
        use_markdown = self.registryValue('markdown', channel=msg.channel, network=irc.network)
        first_line_only = self.registryValue('displayMode', channel=msg.channel, network=irc.network) \
            == 'firstline'
        asyncio.run(self._fetch_wiki(irc, site, query, use_markdown=use_markdown, first_line_only=first_line_only))

    @wrap([getopts({'lang': 'somethingWithoutSpaces'}), 'text'])
    def wiki(self, irc, msg, _args, optlist, searchquery):
        """<search query>

        Returns the first paragraph of a Wikipedia article.
        """
        optlist = dict(optlist)
        lang = optlist.get('lang') or \
            self.registryValue('wikipedia.lang', channel=msg.channel, network=irc.network)

        site = f'https://{lang}.wikipedia.org/'
        self._wiki(irc, msg, site, searchquery)

    @wrap(['somethingWithoutSpaces', 'text'])
    def customwiki(self, irc, msg, _args, site, searchquery):
        """<site> <search query>

        Returns the first paragraph of an article from any MediaWiki site.
        """
        self._wiki(irc, msg, site, searchquery)

Class = Wikifetch
