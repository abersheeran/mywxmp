import xml.etree.ElementTree


def parse_xml(xml_str: str) -> dict[str, str]:
    """
    https://developers.weixin.qq.com/doc/offiaccount/Message_Management/Receiving_standard_messages.html
    """
    root = xml.etree.ElementTree.fromstring(xml_str)
    return {child.tag: child.text or "" for child in root}


def build_xml(data: dict[str, str]) -> str:
    """
    https://developers.weixin.qq.com/doc/offiaccount/Message_Management/Passive_user_reply_message.html
    """
    root = xml.etree.ElementTree.Element("xml")
    for key, value in data.items():
        child = xml.etree.ElementTree.SubElement(root, key)
        child.text = value
    return xml.etree.ElementTree.tostring(root, encoding="unicode", method="xml")
